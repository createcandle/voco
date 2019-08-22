"""Utility functions."""

import subprocess

import time
from time import sleep
from datetime import datetime,timedelta #timezone
#from dateutil.tz import *
from dateutil import tz
from dateutil.parser import *

import requests
import shutil

try:
    #from pytz import timezone
    import pytz
except:
    print("ERROR, pytz is not installed. try 'pip3 install pytz'")


color_dictionary = {
  'black': '#000000',
  'silver': '#c0c0c0',
  'gray': '#808080',
  'white': '#ffffff',
  'maroon': '#800000',
  'red': '#ff0000',
  'purple': '#800080',
  'fuchsia': '#ff00ff',
  'green': '#008000',
  'lime': '#00ff00',
  'olive': '#808000',
  'yellow': '#ffff00',
  'navy': '#000080',
  'blue': '#0000ff',
  'teal': '#008080',
  'aqua': '#00ffff',
  'orange': '#ffa500',
  'alice blue': '#f0f8ff',
  'antique white': '#faebd7',
  'aquamarine': '#7fffd4',
  'azure': '#f0ffff',
  'beige': '#f5f5dc',
  'bisque': '#ffe4c4',
  'blanched almond': '#ffebcd',
  'blue violet': '#8a2be2',
  'brown': '#a52a2a',
  'burlywood': '#deb887',
  'cadet blue': '#5f9ea0',
  'chartreuse': '#7fff00',
  'chocolate': '#d2691e',
  'coral': '#ff7f50',
  'cornflower blue': '#6495ed',
  'corn silk': '#fff8dc',
  'crimson': '#dc143c',
  'cyan': '#00ffff',
  'dark blue': '#00008b',
  'dark cyan': '#008b8b',
  'dark goldenrod': '#b8860b',
  'dark gray': '#a9a9a9',
  'dark green': '#006400',
  'dark grey': '#a9a9a9',
  'dark khaki': '#bdb76b',
  'dark magenta': '#8b008b',
  'dark olive green': '#556b2f',
  'dark orange': '#ff8c00',
  'dark orchid': '#9932cc',
  'dark red': '#8b0000',
  'dark salmon': '#e9967a',
  'dark seagreen': '#8fbc8f',
  'dark slate blue': '#483d8b',
  'dark slate gray': '#2f4f4f',
  'dark slate grey': '#2f4f4f',
  'dark turquoise': '#00ced1',
  'dark violet': '#9400d3',
  'deep pink': '#ff1493',
  'deep sky blue': '#00bfff',
  'dim gray': '#696969',
  'dim grey': '#696969',
  'dodger blue': '#1e90ff',
  'firebrick': '#b22222',
  'floral white': '#fffaf0',
  'forest green': '#228b22',
  'gainsboro': '#dcdcdc',
  'ghost white': '#f8f8ff',
  'gold': '#ffd700',
  'goldenrod': '#daa520',
  'green yellow': '#adff2f',
  'grey': '#808080',
  'honeydew': '#f0fff0',
  'hot pink': '#ff69b4',
  'indian red': '#cd5c5c',
  'indigo': '#4b0082',
  'ivory': '#fffff0',
  'khaki': '#f0e68c',
  'lavender': '#e6e6fa',
  'lavender blush': '#fff0f5',
  'lawn green': '#7cfc00',
  'lemon chiffon': '#fffacd',
  'light blue': '#add8e6',
  'light coral': '#f08080',
  'light cyan': '#e0ffff',
  'light goldenrod yellow': '#fafad2',
  'light gray': '#d3d3d3',
  'light green': '#90ee90',
  'light grey': '#d3d3d3',
  'light pink': '#ffb6c1',
  'light salmon': '#ffa07a',
  'light sea green': '#20b2aa',
  'light sky blue': '#87cefa',
  'light slate gray': '#778899',
  'light slate grey': '#778899',
  'light steel blue': '#b0c4de',
  'light yellow': '#ffffe0',
  'lime green': '#32cd32',
  'linen': '#faf0e6',
  'magenta': '#ff00ff',
  'medium aquamarine': '#66cdaa',
  'medium blue': '#0000cd',
  'medium orchid': '#ba55d3',
  'medium purple': '#9370db',
  'medium sea green': '#3cb371',
  'medium slate blue': '#7b68ee',
  'medium spring green': '#00fa9a',
  'medium turquoise': '#48d1cc',
  'medium violet red': '#c71585',
  'midnight blue': '#191970',
  'mint cream': '#f5fffa',
  'misty rose': '#ffe4e1',
  'moccasin': '#ffe4b5',
  'navajo white': '#ffdead',
  'old lace': '#fdf5e6',
  'olive drab': '#6b8e23',
  'orange red': '#ff4500',
  'orchid': '#da70d6',
  'pale goldenrod': '#eee8aa',
  'pale green': '#98fb98',
  'pale turquoise': '#afeeee',
  'pale violet red': '#db7093',
  'papaya whip': '#ffefd5',
  'peach puff': '#ffdab9',
  'peru': '#cd853f',
  'pink': '#ffc0cb',
  'plum': '#dda0dd',
  'powder blue': '#b0e0e6',
  'rosy brown': '#bc8f8f',
  'royal blue': '#4169e1',
  'saddle brown': '#8b4513',
  'salmon': '#fa8072',
  'sandy brown': '#f4a460',
  'sea green': '#2e8b57',
  'seashell': '#fff5ee',
  'sienna': '#a0522d',
  'sky blue': '#87ceeb',
  'slate blue': '#6a5acd',
  'slate gray': '#708090',
  'slate grey': '#708090',
  'snow': '#fffafa',
  'spring green': '#00ff7f',
  'steel blue': '#4682b4',
  'tan': '#d2b48c',
  'thistle': '#d8bfd8',
  'tomato': '#ff6347',
  'turquoise': '#40e0d0',
  'violet': '#ee82ee',
  'wheat': '#f5deb3',
  'white smoke': '#f5f5f5',
  'yellow green': '#9acd32',
  'rebecca purple': '#663399',
}




def is_a_number(s):
    """ Returns True is string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        return False
    
    
def get_int_or_float(v):
    number_as_float = float(v)
    number_as_int = int(number_as_float)
    if number_as_float == number_as_int:
        return number_as_int
    else:
        
        #tamed_float = float( int(number_as_float * 100) / 100)
        
        return float( int( number_as_float * 100) / 100) 
        #return  float('%.2f' % number_as_float).rstrip('0').rstrip('.')
        #return  round(number_as_float,2)



def get_api_url(link_list):
    for link in link_list:
        #print("link item = " + str(link))
        if link['rel'] == 'property':
            return link['href']
    return None



def clean_up_string_for_speaking(sentence):
    sentence = sentence.replace('/', ' ').replace('\\', ' ').replace('+', ' plus ').replace('#', ' number ').replace('-', ' ').replace('&', ' and ')
    return sentence



def split_sentences(st):
    sentences = re.split(r'[.?!]\s*', st)
    if sentences[-1]:
        return sentences
    else:
        return sentences[:-1]

        

def is_color(color_name):
    if color_name in color_dictionary:
        return True
    return False



def color_name_to_hex(target_color):
    print("target color: " + str(target_color))
    try:
        #hx = next(hex_color for hex_color, value in color_dictionary if value == color_name)
        for current_name,current_hx in color_dictionary:
            if str(current_name) == str(target_color):
                print(str(target_color) + " matched " + str(current_hx))
                return str(current_hx)
    except:
        print("couldn't match spoken color to a hex value. Returning red.")
        return '#ff0000'                                   



def hex_to_color_name(target_hx):
    #hx = next(hex_color for hex_color, value in color_dictionary if value == color_name)
    print("__hex_to_color_name: hex to work with: " + str(target_hx))
    if len(target_hx) == 7 and target_hx.startswith('#'):
        print("very likely a hex color")

        try:
            # if color is found in dict
            try:
                #quick_color_name = next(current_color for current_color, current_hx in color_dictionary if current_hx == target_hx)
                quick_color_name = next(key for key, value in color_dictionary.items() if value == str(target_hx))
                
                #if str(quick_color_name) != "sorry":
                print("quick color match: " + str(quick_color_name))
                return str(quick_color_name)

            except:
                print("Was not able to get a quick hex-to-color match, will try to find a neighbouring color.")

            target_hx = target_hx.replace("#", "")

            # return the closest available color
            m = 16777215
            k = '000000'
            for current_color_name, current_hx in color_dictionary.items():
            #for key in color_dictionary.keys():
                current_hx = current_hx.replace("#", "")

                a = int(target_hx[:2],16)-int(current_hx[:2],16)
                b = int(target_hx[2:4],16)-int(current_hx[2:4],16)
                c = int(target_hx[4:],16)-int(current_hx[4:],16)

                v = a*a+b*b+c*c # simple measure for distance between colors

                # v = (r1 - r2)^2 + (g1 - g2)^2 + (b1 - b2)^2

                if v <= m:
                    print("smaller hex distance: " + str(v))
                    m = v
                    k = current_color_name

            #print("__hex_to_color_name: matched color: " + str(color_dictionary[k]))
            print("__hex_to_color_name: closest matching hex color: " + str(k))
            #slow_color_name = next(key for key, value in color_dictionary.items() if value == str(target_hx))
            return str(k)
        except Exception as ex:
            print("Error while translating hex color to human readable name: " + str(ex))
            return "red"
    else:
        print("String was not a hex color?")
        return target_hx


def download_file(url, target_file):
    print("File to download: " + str(url))
    print("File to save to:  " + str(target_file))
    try:
        #if intended_filename == None:
        intended_filename = target_file.split('/')[-1]
        with requests.get(url, stream=True) as r:
            with open(target_file, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
    except Exception as ex:
        print("ERROR downloading file: " + str(ex))
        return False
    print("download_file: returning. Filename = " + str(intended_filename))
    return True



def run_command(command, cwd=None):
    try:
        return_code = subprocess.call(command, shell=True, cwd=cwd)
        return return_code

    except Exception as ex:
        print("Error running shell command: " + str(ex))
        



def run_command_with_lines(command):
    try:
        p = subprocess.Popen(command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)
        # Read stdout from subprocess until the buffer is empty !
        for bline in iter(p.stdout.readline, b''):
            line = bline.decode('utf-8') #decodedLine = lines.decode('ISO-8859-1')
            line = line.rstrip()
            if line: # Don't print blank lines
                yield line
                
        # This ensures the process has completed, AND sets the 'returncode' attr
        while p.poll() is None:                                                                                                                                        
            sleep(.1) #Don't waste CPU-cycles
        # Empty STDERR buffer
        err = p.stderr.read()
        if p.returncode == 0:
            yield("Command success")
            return True
        else:
            # The run_command() function is responsible for logging STDERR 
            if len(err) > 1:
                yield("Command failed with error: " + str(err.decode('utf-8')))
                return False
            yield("Command failed")
            return False
            #return False
    except Exception as ex:
        print("Error running shell command: " + str(ex))
        
