import os
from pathlib import Path
from uuid import uuid4
from . import myjalali
from django.utils import timezone


def to_persian_number(mystr):
        number = {
            "0": "۰",
            "1": "۱",
            "2": "۲",
            "3": "۳",
            "4": "۴",
            "5": "۵",
            "6": "۶",
            "7": "۷",
            "8": "۸",
            "9": "۹",
        }

        for k, v in number.items():
            mystr = mystr.replace(k, v)

        return mystr


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

    @staticmethod
    def to_jalali(time):
        time = timezone.localtime(time)
        G_time_string = '{}-{}-{}'.format(time.year, time.month, time.day)
        j_month = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر', 'دی', 'بهمن', 'اسفند']
        jtime = myjalali.Gregorian(G_time_string).persian_tuple()
        
        # change tuple to list for mutable
        jtime_list = list(jtime)

        for i, j in enumerate(j_month):
            if jtime_list[1] == i + 1:
                jtime_list[1] = j_month[i]
        output = '{} {} {} ساعت {}:{}'.format(jtime_list[2], jtime_list[1], jtime_list[0], time.strftime('%H'), time.strftime('%M'))
        
        # convert number to persian
        output = to_persian_number(output)
        return output