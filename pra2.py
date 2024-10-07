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


BASE_DIR = '/var/www/html/calendar/'
BOOT_AUDIO_PATH = BASE_DIR + 'upload/booting_audio.mp3'

class AudioPlayer:

    def __init__(self, dir_path, thirukkural_api):
        self.dir_path = dir_path
        self.thirukkural_url_api = thirukkural_api
        self.audio_running_status = 0
        self.pause_control = 0
        self.check = 0
        self.init_pygame()
        self.database_connect()

    def play_audio(self, audio_path, flag):
        """Plays a specified audio file using Pygame mixer."""
        try:
            pyg.mixer.music.load(audio_path)
            pyg.mixer.music.play()
            print("Playing audio-path:", audio_path)
            while pyg.mixer.music.get_busy():
                self.check = 1
                while True and flag and self.check:
                    # get data from api and pause or stop audio
                    audio_status = self.thirukkural_playing()
                    if audio_status:
                        pause_status = int(audio_status["audio_pause_status"])
                        stop_status = int(audio_status["audio_stop_status"])
                        if pause_status == 1:
                            pyg.mixer.music.pause()
                            self.pause_control = 1
                            print("Audio Paused by API status",
                                  self.pause_control)
                        elif pause_status == 0 and self.pause_control:
                            pyg.mixer.music.unpause()
                            self.pause_control = 0
                            print("Audio Resumed by API status",
                                  self.pause_control)
                        elif stop_status == 1:
                            pyg.mixer.music.stop()
                            print("Audio stop by API status",
                                  self.pause_control)
                            break
                        elif not pyg.mixer.music.get_busy() and pause_status == 0:
                            self.check = 0
                            print("Audio Finished by API status",
                                  self.pause_control)
        except Exception as e:
            print("Error playing audio:", audio_path, e)

    def init_pygame(self) -> None:
        ''' Default initialization for pygame '''
        print("Pygame is Import")
        pyg.init()
        pyg.mixer.init()

    def thirukkural_playing(self):
        try:
            response = requests.get(self.thirukkural_url_api)
            response.raise_for_status()
            try:
                data = response.json()
                return data
            except ValueError:
                return None
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

    def database_connect(self):
        try:
            self.connection = pooling.MySQLConnectionPool(
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
            self.connection = None

    def update_audio_status(self, status: int) -> None:
        ''' Updates the audio_running_status in the database '''
        if self.connection is None:
            print("No database connection available")
            return
        try:
            # Get a connection from the pool
            conn = self.connection.get_connection()
            cursor = conn.cursor()

            # Update audio_running_status in the table
            update_query = "UPDATE thirukural_running_status SET audio_running_status = %s WHERE 1"
            cursor.execute(update_query, (status,))
            conn.commit()

            print(f"Audio running status updated to: {status}")
        except mysql.connector.Error as err:
            print(f"Error: {err}")
        finally:
            # Ensure both cursor and connection are closed properly
            if cursor:
                cursor.close()
            if conn:
                conn.close()


    def main(self):
        while True:
            try:
                thirukkural_data = self.thirukkural_playing()
                if thirukkural_data:
                    thirukkural_paths = [thirukkural_data[key]["audio_path"] for key in thirukkural_data if isinstance(
                        thirukkural_data[key], dict) and "audio_path" in thirukkural_data[key]]
                    for thirukkural in thirukkural_paths:
                        file_path = str(self.dir_path) + thirukkural
                        corrected_path = file_path.replace("\\", "/")
                        self.play_audio(corrected_path, True)
                        time.sleep(0.5)
                    self.update_audio_status(0)
            except KeyboardInterrupt:  # Handle program termination gracefully
                pass  # No cleanup needed for pygame in this case



if __name__ == "__main__":
    dir_path = "/var/www/html/calendar/"
    thirukkural_api = "http://localhost/calendar/get_audio_api_test.php"
    Worker2 = AudioPlayer(dir_path, thirukkural_api)
    Worker2.main()