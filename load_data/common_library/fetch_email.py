import logging
from imaplib import IMAP4_SSL
from imaplib import IMAP4
from socket import gaierror

import email
from email import message_from_bytes
from email.message import EmailMessage
from email.header import decode_header
from email.mime.base import MIMEBase
import os
import base64

from typing import List


class FetchEmail():
    
    def __init__(self, host: str, port: int, address: str, password: str) -> object:
        self.__host = host
        self.__port = port
        self.__address = address
        self.__password = password
        
        try:
            self.__imap_host = IMAP4_SSL(host=self.__host, port=self.__port)
            status, response = self.__imap_host.login(self.__address, self.__password)       
            
            logging.info('Установлено подключение к IMAP хосту')
        except gaierror as exc:
            logging.error(f'Указан неверный IMAP хост', exc_info=True)
            raise
        except TimeoutError as exc:
            logging.error(f'Не удалось подключиться к IMAP хосту', exc_info=True)
            raise
        except IMAP4.error as exc:
            logging.error('Не удалось подключиться к IMAP хосту с указанными реквизитами')
            raise
        except Exception as exc:
            logging.error('Непредвиденная ошибка', exc_info=True) 
            raise

    
    def get_email_uids(self, folder: str='INBOX') -> None:
               
        try:
            
            self.__emails = []
            
            result = self.__imap_host.select(folder)
            (status, response) = self.__imap_host.uid('search', 'UNSEEN', 'ALL')
            
            if status == "OK":
                self.__emails = response[0].split()
            
            logging.info(f'Обнаружено непрочитанных писем: {len(self.__emails)}')

        except IMAP4.error as exc:
            exception_description = exc.args[0]
            
            if exception_description == 'command SEARCH illegal in state AUTH, only allowed in states SELECTED':
                logging.error(f'Не найдена указанная папка {folder}', exc_info=True)
            else:
                logging.error(f'Непредвиденная ошибка', exc_info=True)
            
            raise
        except Exception as exc:
            logging.error('Непредвиденная ошибка', exc_info=True)
            raise
    
    
    def __get_message(self, message_uid: bytes) -> EmailMessage:
        
        status, data = self.__imap_host.uid('fetch', message_uid, '(RFC822)')
        
        message_object = message_from_bytes(data[0][1])

        return message_object
    
    
    def save_attachments(self, folder: str, part_types: List[str], select_senders: List[str]=[], select_subjects: List[str]=[]) -> None:
    
        for message_uid in self.__emails:
            
            msg = self.__get_message(message_uid)
            
            from_address = msg['Return-path']

            header = self.get_decoded_text(msg['Subject'])
            
            if (select_senders != [] and from_address in select_senders) and \
                (select_subjects != [] and header in select_subjects): 
            
                for part in msg.walk():
                    
                    part_type = part.get_content_type()
                    
                    if part.get_content_maintype() == 'multipart':
                        continue
                    elif part.get('Content-Disposition') is None:
                        continue
                    elif part_types != [] and not part_type in part_types:
                        continue

                    filename = self.get_decoded_text(part.get_filename())
                    
                    att_path = os.path.join(folder, filename)

                    if os.path.isfile(att_path):
                        logging.warning(f'Файл будет перезаписан {att_path}')

                    with open(att_path, 'wb') as fp:
                        fp.write(part.get_payload(decode=True))
                        
                    self.__imap_host.uid('STORE', message_uid, '+FLAGS', '\SEEN')
                    
                    logging.info(f'Файл успешно сохранен: {att_path}')


    @staticmethod       
    def get_decoded_text(msg_part: str) -> str:
    
        text, encoding = decode_header(msg_part)[0]
        if not encoding is None:
            text = text.decode(encoding)
            
        return text


    def close_connection(self):
        self.__imap_host.close()
        logging.info('Завершено подключение к IMAP хосту')