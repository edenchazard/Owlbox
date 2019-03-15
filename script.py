import RPi.GPIO as GPIO # Import the GPIO Library
import time # Import the Time library
import os
import subprocess 
import picamera

# Set the GPIO modes
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Define GPIO pins to use on the Pi
pinTrigger = 3
pinEcho = 2

# Set pins as output and input
GPIO.setup(pinTrigger, GPIO.OUT)  # Trigger
GPIO.setup(pinEcho, GPIO.IN)      # Echo

#video length in seconds
VIDLEN = 60 * 10

# Tolerance distance for when we think we've hit a bird
DISTANCETOL = 10
YOUTUBE = "rtmp://a.rtmp.youtube.com/live2/"
KEY = ""
BITRATE = 2000000

#cmd = 'ffmpeg -f h264 -r 25 -i - -itsoffset 5.5 -fflags nobuffer -f alsa -ac 1 -i hw:1,0 -vcodec copy -acodec aac -ac 1 -ar 8000 -ab 32k -map 0:0 -map 1:0 -strict experimental -f flv ' + YOUTUBE + KEY
cmd = "raspivid -o - -t 0 -vf -hf -fps 30 -b 6000000 | avconv -re -ar 44100 -ac 2 -acodec pcm_s16le -f s16le -ac 2 -i /dev/zero -f h264 -i - -vcodec copy -acodec aac -ab 128k -g 50 -strict experimental -f flv rtmp://a.rtmp.youtube.com/live2/"+KEY
print (cmd)

def sensor():
    # Set trigger to False (Low)
    GPIO.output(pinTrigger, False)

    # Allow module to settle
    time.sleep(0.5)

    # Send 10us pulse to trigger
    GPIO.output(pinTrigger, True)
    time.sleep(0.00001)
    GPIO.output(pinTrigger, False)

    # Start the timer
    StartTime = time.time()

    # The start time is reset until the Echo pin is taken high (==1)
    while GPIO.input(pinEcho)==0:
        StartTime = time.time()

    # Stop when the Echo pin is no longer high - the end time
    while GPIO.input(pinEcho)==1:
        StopTime = time.time()
        # If the sensor is too close to an object, the Pi cannot
        # see the echo quickly enough, so we have to detect that
        # problem and say what has happened.
        if StopTime-StartTime >= 0.04:
            print("too close")
            StopTime = StartTime
            break

    # Calculate pulse length
    ElapsedTime = StopTime - StartTime

    # Distance pulse travelled in that time is
    # time multiplied by the speed of sound (cm/s)
    Distance = ElapsedTime * 34326

    # That was the distance there and back so halve the value
    Distance = Distance / 2
    
    return Distance
try:
    while True:
        distance = sensor()

        print("Distance: %.1f cm" % distance)

        # The initial trigger to start us up
        if(distance <= DISTANCETOL):
            print( "Bird Found, opening camera and starting stream" )
            
            stream_pipe = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE) 
            camera = picamera.PiCamera(resolution=(640, 480), framerate=25)
            camera.vflip = True 
            camera.hflip = True
             
            camera.start_recording(stream_pipe.stdin, format='h264', bitrate = BITRATE)
            time.sleep(VIDLEN)
    
            # Continously evaluate whether we need to
            # continue recording OR end the stream
            # To do this we test the sensor every VIDLEN
            while True:
                retry = sensor()

                # Bird still in sight!
                if(retry <= DISTANCETOL):
                    camera.wait_recording(VIDLEN)
                # Once distance is out of range, end the video.
                else:
                    print( "Stopping video, closing camera" )
                    camera.stop_recording()
                    camera.close()
                    stream_pipe.stdin.close()
                    stream_pipe.wait()
                    break #Exit the loop
        time.sleep(0.7)

# If you press CTRL+C, cleanup and stop
except KeyboardInterrupt:
    print ("CTRL-C pressed, closing")
    
finally:
    print ("Shutdown.")
    camera.stop_recording()
    camera.close()
    stream_pipe.stdin.close()
    stream_pipe.wait()
    # Reset GPIO settings
    GPIO.cleanup()