import base64
import cv2
import time
import requests
import operator
import numpy as np
import cognitive_face as cf
import os
from collections import Counter
from imgurpython import ImgurClient
import Tkinter as tk
from itertools import cycle

from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

# import sys
# reload(sys)
# sys.setdefaultencoding('utf-8')


SOCKET = '<redacted>'


GROUP_MODE = False


FACE_API_KEY = '<redacted>'
EMOTION_API_KEY = '<redacted>'

IMGUR_ID = '<redacted>'
IMGUR_SECRET = '<redacted>'

BEARD_THRESHOLD = 0.4

MAX_NUM_RETRY = 10
EMOTION_ENDPOINT = '<redacted>'

IMG_PATH = os.getcwd() + '/images/'


img_client = ImgurClient(IMGUR_ID, IMGUR_SECRET)
cf.Key.set(FACE_API_KEY)

def save_webcam_frame():
	vc = cv2.VideoCapture(0)
	time.sleep(0.5)
	_, frame = vc.read()
	img_name = 'test.jpg'
	cv2.imwrite(img_name, frame)
	path = os.getcwd()

	return path + '/' + img_name

def get_image_info():
	has_person = False
	img_path = save_webcam_frame()
	img_info = img_client.upload_from_path(img_path)
	img_id = img_info['deletehash']
	img_url = img_info['link']

	print('============================')
	print('Delete hash: \t\t' + img_id)
	print('Image link: \t\t' + img_url)
	print('============================')


	# face API
	face_result = cf.face.detect(
		image=img_url,
		attributes='age,gender,smile,facialHair,glasses'
	)

	# emotion API
	headers = dict()
	headers['Ocp-Apim-Subscription-Key'] = EMOTION_API_KEY
	headers['Content-Type'] = 'application/json'
	json = { 'url': img_url } 
	data = None
	params = None
	emotion_result = processRequest(json, data, headers, params)
	
	img_client.delete_image(img_id)
	print('IMAGE DELETED.')
	print('============================')

	face_info = None
	emotion_info = None

	if len(face_result) > 0:
		total_age = 0
		num_female = 0
		all_hair = 0
		num_glasses = 0

		for face in face_result:
			face_attr = face['faceAttributes']
			total_age += face_attr['age']
			num_female += 1 if face_attr['gender'] == 'female' else 0
			all_hair += sum(face_attr['facialHair'][score] for score in face_attr['facialHair'])
			num_glasses = 0 if face_attr['glasses'] == 'NoGlasses' else 1

		num_male = len(face_result) - num_female
		no_glasses = len(face_result) - num_glasses

		avg_age = total_age / len(face_result)
		dominant_gender = 'female' if num_female >= num_male else 'male' # arbitrary tie breaking
		avg_hair = all_hair / len(face_result)
		avg_glasses = True if num_glasses >= no_glasses else False

		face_info = (avg_age, dominant_gender, avg_hair, avg_glasses)

	if len(emotion_result) > 0:

		cumul_emotion = Counter()

		for person in emotion_result:
			for emotion in person['scores']:
				cumul_emotion[emotion] += person['scores'][emotion]

		emotion_info = cumul_emotion

	return len(face_result), face_info, emotion_info

def get_dominant_emotion(emotion_info):
	max_value = -1
	dominant_emotion = None

	for emotion in emotion_info:
		emotion_value = emotion_info[emotion]

		if emotion_value > max_value:
			max_value = emotion_value
			dominant_emotion = emotion

	return dominant_emotion

def is_wearing_glasses(face_info):
	_, _, _, avg_glasses = face_info
	return avg_glasses

def has_some_beard(face_info):
	_, _, avg_hair, _ = face_info
	return avg_hair >= BEARD_THRESHOLD

def is_neutral(dominant_emotion):
	return dominant_emotion == 'neutral'

def is_female(face_info):
	_, dominant_gender, _, _ = face_info
	return dominant_gender == 'female'

def is_happy(dominant_emotion):
	return dominant_emotion == 'happiness'

def is_not_feeling_well(dominant_emotion):
	return not is_neutral(dominant_emotion) and not is_happy(dominant_emotion)

def print_face_info(face_info):
	avg_age, dominant_gender, avg_hair, avg_glasses = face_info
	print('Average Age: \t\t{}'.format(avg_age))
	print('Dominant Gender: \t{}'.format(dominant_gender.upper()))
	print('Facial Hair: \t\t{}'.format(has_some_beard(face_info)))
	print('Wearing glasses: \t{}'.format(avg_glasses))

def print_dominant_emotion(dominant_emotion):
	print('Dominan emotion: \t{}'.format(dominant_emotion.upper()))

def print_num_people(num_people):
	print('Number of People: \t{}'.format(num_people))

def get_image_generator():
	while True:
		num_people, face_info, emotion_info = get_image_info()

		if face_info:
			# human is on the image
			print_num_people(num_people)
			dominant_emotion = get_dominant_emotion(emotion_info)
			# print(dominant_emotion)
			print_dominant_emotion(dominant_emotion)
			print_face_info(face_info)

			if GROUP_MODE and num_people > 1:
				# handle group case
				pass
			else:
				# single person case
				if is_not_feeling_well(dominant_emotion):
					# depression support ads
					yield 'depression'
				else:
					if is_wearing_glasses(face_info):
						# neutral wearing glasses
						# img_path = IMG_PATH + 'glasses.gif'
						yield 'glasses'
					elif has_some_beard(face_info):
						# has beard
						yield 'beard'
					elif is_female(face_info):
						# female no glasses no beard
						yield 'female'
					else:
						# male no glasses no beard
						yield 'male'


				
		else:
			# power saving mode here
			print('ENTERING POWER SAVING MODE')
			yield 'power_save_mode'

# def get_pil_photos_generator(image_generator):
# 	for image_file in image_generator:
# 		# yield ImageTk.PhotoImage(file=image_file)
# 		yield (tk.PhotoImage(file=image_file), image_file)

gen = get_image_generator()

def send_new_image_to_client(client, server):
	new_image = next(gen)
	server.send_message_to_all(new_image)

class SimpleEcho(WebSocket):
	def handleMessage(self):
		# echo message back to client
		print('message received!')
		self.sendMessage(next(gen))

	def handleConnected(self):
		print self.address, 'opened'

	def handleClose(self):
		print self.address, 'closed'

def main():
	
	server = SimpleWebSocketServer('', 13254, SimpleEcho)
	print('running')
	server.serveforever()	


def processRequest(json, data, headers, params):
	retries = 0
	result = None

	while True:
		response = requests.request('post', EMOTION_ENDPOINT, json = json, data = data, headers = headers, params = params)

		if response.status_code == 429: 
			print('Message: {}'.format(response.json()['error']['message']))

			if retries <= MAX_NUM_RETRY: 
				time.sleep(1) 
				retries += 1
				continue
			else: 
				print('Error: failed after retrying!')
				break

		elif response.status_code == 200 or response.status_code == 201:
			if 'content-length' in response.headers and int(response.headers['content-length']) == 0: 
				result = None 
			elif 'content-type' in response.headers and isinstance(response.headers['content-type'], str): 
				if 'application/json' in response.headers['content-type'].lower(): 
					result = response.json() if response.content else None 
				elif 'image' in response.headers['content-type'].lower(): 
					result = response.content
		else:
			print('Error code: {}'.format(response.status_code))
			print('Message: {}'.format(response.json()['error']['message']))

		break

	return result


if __name__ == '__main__':
	main()
