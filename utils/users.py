import os
import random
import json

CONFIG_NAME = 'users'

class BotUser(object):
    def __init__(self, user_id: str, user_name: str, entrance_filename:str=None, birthday:str=None):
        self.user_id = user_id
        self.user_name = user_name
        self.entrance_filename = entrance_filename
        self.birthday = birthday

    def add_entrance(self, entrance_filename):
        self.entrance_filename = entrance_filename

    def add_birthday(self, birthday):
        self.birthday = birthday

class UserManager():
    def __init__(self, user_repo):
        self.users = []
        self.user_repo = user_repo
        self.users_json_file = self.user_repo.find(CONFIG_NAME)

        if self.users_json_file is None:
            self.users_json_file = self.user_repo.add_file(filename=f'{CONFIG_NAME}.json')
        else:
            self._load_users()


    def _load_users(self):
        print(f'Loading user json from {self.users_json_file.path}')

        with open(self.users_json_file.path, 'r', encoding='utf-8') as json_txt:
            users_json = json.load(json_txt)
            self.users = [BotUser(
                user_id=u['user_id'], 
                user_name=u['user_name'], 
                entrance_filename=u['entrance_filename'],
                birthday=u['birthday']
            ) for u in users_json]

        print('Load complete')


    def _save_user_json(self):
        print(f'Saving user json to {self.users_json_file.path}')

        with open(self.users_json_file.path, 'w', encoding='utf-8') as f:
            json.dump([u.__dict__ for u in self.users], f, indent=4, ensure_ascii=False)

        print('Save complete')

        self.user_repo.update_file(file_obj=self.users_json_file)


    def add_user(self, user_id, user_name, save=True):
        self.users.append(BotUser(user_id=user_id, user_name=user_name))
        
        if save:
            self._save_user_json()
        

    def add_users(self, bot_users):
        if len(bot_users) == 0:
            return
            
        for user in bot_users:
            self.add_user(user_id=user.user_id, user_name=user.user_name, save=False)
        
        self._save_user_json()


    def add_entrance(self, user_id, entrance_sound):
        user = self.get_user(user_id)

        if not user:
            return

        user.add_entrance(entrance_sound)
        self._save_user_json()


    def add_birthday(self, user_id, birthday):
        user = self.get_user(user_id)

        if not user:
            return

        user.add_birthday(birthday)
        self._save_user_json()   


    def get_user(self, user_id):
        return next((f for f in self.users if f.user_id == user_id), None)        