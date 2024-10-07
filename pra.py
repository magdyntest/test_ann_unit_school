import os
import signal
import RPi.GPIO as GPIO
import time
import pygame as pyg
import requests
import mysql.connector
from mysql.connector import pooling
import threading
import multiprocessing
import pyttsx3
from gtts import gTTS
import socket
import os
import tempfile

BASE_DIR = '/var/www/html/calendar/'
BOOT_AUDIO_PATH = BASE_DIR + 'upload/booting_audio.mp3'


class BCDThumbwheel:
    def __init__(self, dirpath, thirukkural_api):
        self.arr1 = [6, 13, 19, 26]
        self.arr2 = [12, 16, 20, 21]
        self.arr3 = [24, 25, 8, 7]
        self.arr4 = [4, 17, 27, 22]
        self.diff = 15
        self.pushbutton = 5
        self.previous_audio_data = None
        self.dir_path = dirpath
        self.url = thirukkural_api
        self.setup_pins()
        self.database_connect()
        self.init_pygame()

    def init_pygame(self) -> None:
        ''' Default initialization for pygame '''
        print("Pygame initialized")
        pyg.init()
        pyg.mixer.init()

    def setup_pins(self):
        """Sets up GPIO pins as inputs with pull-up resistors."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pushbutton, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        for pin in self.arr1 + self.arr2 + self.arr3 + self.arr4:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        time.sleep(0.5)  # Ensure all pins are properly set up

    def read_array(self, arr):
        """Reads the GPIO input values for a given array of pins and calculates the total."""
        total = 0
        for i, pin in enumerate(arr):
            if GPIO.input(pin) == GPIO.HIGH:
                total += 2**i
        return total

    def read_switches(self):
        """Reads all switch arrays and returns the calculated string based on the 'diff' value."""
        total1 = self.read_array(self.arr1)
        total2 = self.read_array(self.arr2)
        total3 = self.read_array(self.arr3)
        total4 = self.read_array(self.arr4)
        return f"{abs(total1 - self.diff)}{abs(total2 - self.diff)}{abs(total3 - self.diff)}{abs(total4 - self.diff)}"

    def handle(self, value):
        if value >= 1 and value <= 1330:
            return value
        elif value >= 2001 and value <= 2133:
            return value
        elif value >= 3001 and value <= 3003:
            return value
        elif value >= 4001 and value <= 4085:
            return value
        elif value == 0000:
            return str("0000")
        else:
            return None

    def database_connect(self):
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="mypool",
                pool_size=5,
                pool_reset_session=True,
                host="localhost",
                user="root",
                password="root",
                database="timebase_sys"
            )
            print("Connection pool created successfully")
        except mysql.connector.Error as err:
            print(f"Error creating connection pool: {err}")
            self.pool = None

    def get_data_from_database(self, bcd_number):
        if self.pool:
            connection = self.pool.get_connection()
            cursor = connection.cursor()
            query = "SELECT p_path, a_path, audiopath, t_path FROM bcd1 WHERE bcdnumber = %s"
            cursor.execute(query, (str(bcd_number),))
            results = cursor.fetchall()
            connection.close()
            return results
    
    def get_data_from_api(self):
        try:
            response = requests.get(self.url)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None
        
    def get_ip_address(self):
        """
        Retrieves the IP address of the local machine without dots.
        Returns:
            str: The IP address in a format like '19216811'.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address # Remove dots
        except Exception as e:
            return "192.168.1.0"

    def play_audio(self, audio_path):
        if audio_path:
            try:
                pyg.mixer.music.load(audio_path)
                pyg.mixer.music.play()
                print("Playing audio:", audio_path)
                while pyg.mixer.music.get_busy():
                    pyg.time.wait(100)
                pyg.mixer.music.unload()
            except Exception as e:
                print("Error playing audio:", audio_path, e)


    def play_text(self,text):
        tts = gTTS(text=text, lang='en')
        audio_file = "audio.mp3"
        tts.save(audio_file)
        self.play_audio(audio_file)
        os.remove(audio_file)

    def main(self):
        self.play_audio(BOOT_AUDIO_PATH)
        try:
            while True:
                audio_data = self.get_data_from_api()
                if GPIO.input(self.pushbutton) == False:
                    switch_value = self.handle(int(self.read_switches()))
                    print("Switch value:", switch_value)
                    if int(switch_value) == 0000:
                        print("0000 is presss")
                        try:
                            self.play_text(self.get_ip_address())
                        except:
                            pass
                    if isinstance(switch_value, int):
                        data = self.get_data_from_database(switch_value)
                        for row in data:
                            p_path, a_path, audiopath, t_path = row
                            paths_to_play = [p_path, a_path, audiopath] + t_path.split(',')
                            for audio_file in paths_to_play:
                                audio_file = audio_file.strip()
                                if audio_file:
                                    full_path = f"{self.dir_path}{audio_file}"
                                    self.play_audio(full_path)
                    del switch_value  # Clear the variable
                if audio_data and audio_data != self.previous_audio_data:
                    self.previous_audio_data = audio_data
                    for audio_item in audio_data:
                        audio_paths = [audio_item.get(key) for key in ['bell_path', 'paalpath', 'adhikaram_path', 'thirukkural_path', 'audio'] if audio_item.get(key)]
                        for audio_path in audio_paths:
                            full_audio_path = os.path.join(self.dir_path, audio_path)
                            self.play_audio(full_audio_path)
        except KeyboardInterrupt:
            GPIO.cleanup()
            print("GPIO cleanup complete.")



if __name__ == "__main__":
    api_url = 'http://localhost/calendar/fetchapi.php'
    dir_path = "/var/www/html/calendar/"
    thirukkural_api = "http://localhost/calendar/get_audio_api_test.php"


    player = BCDThumbwheel(dir_path,api_url)

    player.main()

    print("All processes have been terminated.")
