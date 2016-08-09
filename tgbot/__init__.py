import telegram
import multiprocessing
import threading
import Queue
import math

from async.processes import ReceiveProcess
from async.workers import WorkerPool
from entities import dialogue
import events
import logging


class Bot(object):
    def __init__(self, token):
        self.token = token

        self.events_worker_pool = WorkerPool(20)
        self.api_worker_pool = WorkerPool(20)

        self.api = telegram.AsyncBotAPI(token, self.api_worker_pool)

        self.updates = multiprocessing.Queue()
        self.receiver = ReceiveProcess(token, self.updates)

        self.chats = {}
        self.users = {}

        self.init_events()

    def init_events(self):
        self.on_message = events.MessageEvent(self.events_worker_pool)
        self.on_audio = events.AsyncEvent(self.events_worker_pool)
        self.on_document = events.AsyncEvent(self.events_worker_pool)
        self.on_photo = events.AsyncEvent(self.events_worker_pool)
        self.on_sticker = events.AsyncEvent(self.events_worker_pool)
        self.on_video = events.AsyncEvent(self.events_worker_pool)
        self.on_voice = events.AsyncEvent(self.events_worker_pool)


    def process_message(self, chat, user, message):
        if message.is_audio():
            self.on_audio.emit(chat, user, message)
        elif message.is_document():
            self.on_document.emit(chat, user, message)
        elif message.is_photo():
            self.on_photo.emit(chat, user, message)
        elif message.is_sticker():
            self.on_sticker.emit(chat, user, message)
        elif message.is_video():
            self.on_video.emit(chat, user, message)
        elif message.is_voice():
            self.on_voice.emit(chat, user, message)
        elif message.is_service_message():
            pass #TODO
        else:
            self.on_message.emit(chat, user, message)

    def process_update(self, update):
        if update["message"] != None:
            message_data = update["message"]
            self.process_message(
                self.get_chat_from_message_data(message_data),
                self.get_user_from_message_data(message_data),
                dialogue.Message.build(message_data, self.api)
            )

    def get_user_from_message_data(self, message_data):
        if "from" not in message_data: return None
        user_data = message_data["from"]
        id = user_data["id"]
        if id in self.users:
            self.users[id].update_properties(user_data)
            return self.users[id]
        self.users[id] = dialogue.User.build(user_data)
        return self.users[id]

    def get_chat_from_message_data(self, message_data):
        chat_data = message_data["chat"]
        id = chat_data["id"]
        if id in self.chats:
            self.chats[id].update_properties(chat_data)
            return self.chats[id]
        self.chats[id] = dialogue.Chat.build(chat_data, self.api)
        return self.chats[id]

    def process_updates(self):
        while True:
            try:
                update = self.updates.get(True, 5)
            except Queue.Empty:
                continue
            if update == None: break # Receive process sent stop signa
            self.process_update(update)

    def start(self):
        logging.info("Bot is starting")
        self.receiver.start()
        self.events_worker_pool.start()
        self.api_worker_pool.start()
        try:
            self.process_updates()
        except KeyboardInterrupt: pass
        finally:
            self.stop()

    def stop(self):
        logging.info("Bot is stopping")
        self.receiver.terminate()
        self.receiver.join()
        self.events_worker_pool.stop()
        self.api_worker_pool.stop()
