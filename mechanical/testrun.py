# Author: Quyen Lu, Kevin Lieng, Seung Min Song
# License: Public Domain

import time
import board
import busio

from threading import Thread
# Import the ADS1x15 module.
#import Adafruit_ADS1x15
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

from gps import *
import time

import pyrebase

def database_gps(lat, lon, time, speed):
    config = {
        "apiKey" : "apikey goes here",
        "authDomain" : "firebase domain goes here",
        "databaseURL" : "database URL goes here",
        "storageBucket" : "database storage link goes here"}
    
    firebase = pyrebase.initialize_app(config)
    db = firebase.database()
    
    if lat != 0.0 or lon != 0.0 or time != '' or speed != 'nan':
        #Write GPS to database
        gps = {"laditude" : str(lat), "longitude" : str(lon),
               "vehicle_speed" : str(int(speed)), "time" : time}
        db.child("Ambulance").update(gps)
        
def database_pulse(bmp):
    config = {
        "apiKey" : "apikey goes here",
        "authDomain" : "firebase domain goes here",
        "databaseURL" : "database URL goes here",
        "storageBucket" : "database storage link goes here"}
    
    firebase = pyrebase.initialize_app(config)
    db = firebase.database()
    
    if bmp > 0:
        #Write BMP to database
        bmp = {"heart_rate": str(int(bmp))}
        db.child("Ambulance").update(bmp)
  
def gps_reading():
    gpsd = gps(mode=WATCH_ENABLE|WATCH_NEWSTYLE)
    while True:
        report = gpsd.next()
        
        if report['class'] == 'TPV':
            lat = getattr(report, 'lat', 0.0)
            lon = getattr(report, 'lon', 0.0)
            dtime = getattr(report, 'time', '')
            speed = getattr(report, 'speed', 'nan')
            
            database_gps(lat, lon, dtime, speed)
            print(lat,"\t", lon, "\t", dtime,"\t", speed, "\t")
            time.sleep(5)
            
def pulse_reading():
    #adc = Adafruit_ADS1x15.ADS1015()
    i2c = busio.I2C(board.SCL, board.SDA)
    # initialization 
    GAIN = 2/3  

    adc = ADS.ADS1015(i2c, GAIN)
    
    chan = AnalogIn(adc, ADS.P0)


    curState = 0
    thresh = 525  # mid point in the waveform
    P = 512
    T = 512
    stateChanged = 0
    sampleCounter = 0
    lastBeatTime = 0
    firstBeat = True
    secondBeat = False
    Pulse = False
    IBI = 600
    rate = [0]*10
    amp = 100
    
    BMP = 0
    lat = 0
    lon = 0
    dtime = ''
    speed = 'nan'

    lastTime = int(time.time()*1000)

    # Main loop. use Ctrl-c to stop the code
    while True:
        # read from the ADC
        
        #TODO: Select the correct ADC channel. I have selected A0 here
        Signal = chan.value
        curTime = int(time.time()*1000)

        sampleCounter += curTime - lastTime;      #                   # keep track of the time in mS with this variable
        lastTime = curTime
        N = sampleCounter - lastBeatTime;     #  # monitor the time since the last beat to avoid noise
        #print N, Signal, curTime, sampleCounter, lastBeatTime

        ##  find the peak and trough of the pulse wave
        if Signal < thresh and N > (IBI/5.0)*3.0 :  #       # avoid dichrotic noise by waiting 3/5 of last IBI
            if Signal < T :                        # T is the trough
              T = Signal;                         # keep track of lowest point in pulse wave 

        if Signal > thresh and  Signal > P:           # thresh condition helps avoid noise
            P = Signal;                             # P is the peak
                                                # keep track of highest point in pulse wave

          #  NOW IT'S TIME TO LOOK FOR THE HEART BEAT
          # signal surges up in value every time there is a pulse
        if N > 250 :                                   # avoid high frequency noise
            if  (Signal > thresh) and  (Pulse == False) and  (N > (IBI/5.0)*3.0)  :       
              Pulse = True;                               # set the Pulse flag when we think there is a pulse
              IBI = sampleCounter - lastBeatTime;         # measure time between beats in mS
              lastBeatTime = sampleCounter;               # keep track of time for next pulse

              if secondBeat :                        # if this is the second beat, if secondBeat == TRUE
                secondBeat = False;                  # clear secondBeat flag
                for i in range(0,10):             # seed the running total to get a realisitic BPM at startup
                  rate[i] = IBI;                      

              if firstBeat :                        # if it's the first time we found a beat, if firstBeat == TRUE
                firstBeat = False;                   # clear firstBeat flag
                secondBeat = True;                   # set the second beat flag
                continue                              # IBI value is unreliable so discard it


              # keep a running total of the last 10 IBI values
              runningTotal = 0;                  # clear the runningTotal variable    

              for i in range(0,9):                # shift data in the rate array
                rate[i] = rate[i+1];                  # and drop the oldest IBI value 
                runningTotal += rate[i];              # add up the 9 oldest IBI values

              rate[9] = IBI;                          # add the latest IBI to the rate array
              runningTotal += rate[9];                # add the latest IBI to runningTotal
              runningTotal /= 10;                     # average the last 10 IBI values 
              BPM = 60000/runningTotal;               # how many beats can fit into a minute? that's BPM!
              database_pulse(BPM)
              print('BPM: {}'.format(BPM))
              

        if Signal < thresh and Pulse == True :   # when the values are going down, the beat is over
            Pulse = False;                         # reset the Pulse flag so we can do it again
            amp = P - T;                           # get amplitude of the pulse wave
            thresh = amp/2 + T;                    # set thresh at 50% of the amplitude
            P = thresh;                            # reset these for next time
            T = thresh;

        if N > 2500 :                          # if 2.5 seconds go by without a beat
            thresh = 512;                          # set thresh default
            P = 512;                               # set P default
            T = 512;                               # set T default
            lastBeatTime = sampleCounter;          # bring the lastBeatTime up to date        
            firstBeat = True;                      # set these to avoid noise
            secondBeat = False;                    # when we get the heartbeat back
            print("no beats found")

        
        time.sleep(0.05)
    
if __name__ == '__main__':
    Thread(target=gps_reading).start()
    Thread(target=pulse_reading).start()



