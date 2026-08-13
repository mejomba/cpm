import os
from pathlib import Path
from uuid import uuid4


class Utils:
    def __init__(self):
        pass

    @staticmethod
    def user_image_path(instance, filename: str):
        """generate file path for user profile image"""
        ext = filename.split('.')[-1]
        filename = f'{uuid4()}.{ext}'
        directory = f'uploads/images/user'
        Path(directory).mkdir(parents=True, exist_ok=True)
        return os.path.join('uploads/images/user/', filename)

    @staticmethod
    def generic_image_path(instance, filename: str):
        """generate file path for generic image model"""
        ext = filename.split('.')[-1]
        filename = f'{uuid4()}.{ext}'
        sub_folder = instance.__class__.__name__
        directory = f'uploads/images/{sub_folder}'
        Path(directory).mkdir(parents=True, exist_ok=True)
        return os.path.join(f'uploads/images/{sub_folder}/', filename)

    @staticmethod
    def generic_file_path(instance, filename: str):
        """generate file path for generic file model"""
        ext = filename.split('.')[-1]
        filename = f'{uuid4()}.{ext}'
        sub_folder = instance.__class__.__name__
        directory = f'uploads/files/{sub_folder}'
        Path(directory).mkdir(parents=True, exist_ok=True)
        return os.path.join(f'uploads/files/{sub_folder}/', filename)