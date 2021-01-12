"""Utility functions."""



import re
import time
import shutil
import socket
import random
import string
import requests
from requests.adapters import HTTPAdapter
import subprocess
from time import sleep
from dateutil import tz
#from dateutil.tz import *
from dateutil.parser import *
from datetime import datetime,timedelta #timezone



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
    #print("number_as_float=" + str(number_as_float))
    #print("number_as_int=" + str(number_as_int))
    
    if round(v) != v:
        #print("vvvv float")
        return float( int( number_as_float * 100) / 100) 
    else:
        #print("vvvv int")
        return number_as_int
    
    if str(number_as_float) == str(number_as_int):
        #print("--int was same as float")
        return number_as_int
    else:
        #print("--int was NOT the same as float")
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
    sentence = sentence.replace('/', ' ').replace('\\', ' ').replace('+', ' plus ').replace('#', ' number ').replace('-', ' ').replace('&', ' and ').replace('  ', ' ')
    sentence = sentence.replace('  ', ' ')
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
    #print("__hex_to_color_name: hex to work with: " + str(target_hx))
    if len(target_hx) == 7 and target_hx.startswith('#'):
        #print("very likely a hex color")

        try:
            # if color is found in dict
            try:
                #quick_color_name = next(current_color for current_color, current_hx in color_dictionary if current_hx == target_hx)
                quick_color_name = next(key for key, value in color_dictionary.items() if value == str(target_hx))
                
                #if str(quick_color_name) != "sorry":
                #print("quick color match: " + str(quick_color_name))
                return str(quick_color_name)

            except:
                pass
                #print("Was not able to get a quick hex-to-color match, will try to find a neighbouring color.")

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
                    #print("smaller hex distance: " + str(v))
                    m = v
                    k = current_color_name

            #print("__hex_to_color_name: matched color: " + str(color_dictionary[k]))
            #print("__hex_to_color_name: closest matching hex color: " + str(k))
            #slow_color_name = next(key for key, value in color_dictionary.items() if value == str(target_hx))
            return str(k)
        except Exception as ex:
            print("Error while translating hex color to human readable name: " + str(ex))
            return "red"
    else:
        #print("String was not a hex color?")
        return target_hx


def download_file(url, target_file):
    #print("File to download: " + str(url))
    #print("File to save to:  " + str(target_file))
    try:
        #if intended_filename == None:
        intended_filename = target_file.split('/')[-1]
        with requests.get(url, stream=True) as r:
            with open(target_file, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
    except Exception as ex:
        print("ERROR downloading file: " + str(ex))
        return False
    #print("download_file: returning. Filename = " + str(intended_filename))
    return True



#def run_command(command, cwd=None):
#    try:
#        return_code = subprocess.call(command, shell=True, cwd=cwd)
#        return return_code
#
#    except Exception as ex:
#        print("Error running shell command: " + str(ex))
        

def run_command(cmd, timeout_seconds=20):
    try:
        p = subprocess.run(cmd, timeout=timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

        if p.returncode == 0:
            return p.stdout # + '\n' + "Command success" #.decode('utf-8')
            #yield("Command success")
        else:
            if p.stderr:
                return "Error: " + str(p.stderr) # + '\n' + "Command failed"   #.decode('utf-8'))

    except Exception as e:
        print("Error running command: "  + str(e))




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
        





def get_audio_controls():

    audio_controls = []
    
    aplay_result = run_command('aplay -l') 
    lines = aplay_result.splitlines()
    device_id = 0
    previous_card_id = 0
    for line in lines:
        if line.startswith( 'card ' ):
            
            try:
                #print(line)
                line_parts = line.split(',')
            
                line_a = line_parts[0]
                #print(line_a)
                line_b = line_parts[1]
                #print(line_b)
            except:
                continue
            
            card_id = int(line_a[5])
            #print("card id = " + str(card_id))
            
            
            if card_id != previous_card_id:
                device_id = 0
            
            #print("device id = " + str(device_id))
            
            
            simple_card_name = re.findall(r"\:([^']+)\[", line_a)[0]
            simple_card_name = str(simple_card_name).strip()
            
            #print("simple card name = " + str(simple_card_name))
            
            full_card_name   = re.findall(r"\[([^']+)\]", line_a)[0]
            #print("full card name = " + str(full_card_name))
            
            full_device_name = re.findall(r"\[([^']+)\]", line_b)[0]
            #print("full device name = " + str(full_device_name))
            
            human_device_name = str(full_device_name)
            
            # Raspberry Pi 4
            human_device_name = human_device_name.replace("bcm2835 ALSA","Built-in headphone jack")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI","Built-in video")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI1","Built-in video two")
            
            # Raspberry Pi 3
            human_device_name = human_device_name.replace("bcm2835 Headphones","Built-in headphone jack")
            
            # ReSpeaker dual microphone pi hat
            human_device_name = human_device_name.replace("bcm2835-i2s-wm8960-hifi wm8960-hifi-0","ReSpeaker headphone jack")
            #print("human device name = " + human_device_name)
            
            
            control_name = None
            complex_control_id = None
            complex_max = None
            complex_count = None
            
            amixer_result = run_command('amixer -c ' + str(card_id) + ' scontrols') 
            lines = amixer_result.splitlines()
            #print(str(lines))
            #print("amixer lines array length: " + str(len(lines)))
            if len(lines) > 0:
                for line in lines:
                    if "'" in line:
                        #print("maxier controls line = " + line)
                        control_name = re.findall(r"'([^']+)'", line)[0]
                        #print("control name = " + control_name)
                        if control_name is not 'mic':
                            break
                        else:
                            continue # in case the first control is 'mic', ignore it.
                    else:
                        control_name = None
            
            # if there is no 'simple control', then a backup method is to get the normal control options.  
            else:
                #print("get audio controls: no simple control found, getting complex one instead")
                #line_counter = 0
                amixer_result = run_command('amixer -c ' + str(card_id) + ' controls')
                lines = amixer_result.splitlines()
                if len(lines) > 0:
                    for line in lines:
                        #line_counter += 1
                        
                        line = line.lower()
                        #print("line.lower = " + line)
                        if "playback" in line:
                            #print("playback spotted")
                            
                            numid_part = line.split(',')[0]
                            
                            if numid_part.startswith("numid="):
                                numid_part = numid_part[6:]
                                #print("numid_part = " + str(numid_part))
                            
                                #complex_max = 36
                                complex_count = 1 # mono
                                complex_control_id = int(numid_part)
                                #print("complex_control_id = " + str(complex_control_id))
                            
                                info_result = run_command('amixer -c ' + str(card_id) + ' cget numid=' + str(numid_part)) #amixer -c 1 cget numid=
                            
                                if 'values=2' in info_result:
                                    complex_count = 2 # stereo
                                
                                info_result_parts = info_result.split(',')
                                for info_part in info_result_parts:
                                    if info_part.startswith('max='):
                                        complex_max = int(info_part[4:])
                                        #complex_max = int(part)
                                        #break
                                        
                                
                            
                            break
                            
                else:
                    print("getting audio volume in complex way failed") 
                            
                            
                
            
                
            if control_name is 'mic':
                control_name = None
            
            audio_controls.append({'card_id':card_id, 
                                'device_id':device_id, 
                                'simple_card_name':simple_card_name, 
                                'full_card_name':str(full_card_name), 
                                'full_device_name':str(full_device_name), 
                                'human_device_name':str(human_device_name), 
                                'control_name':control_name,
                                'complex_control_id':complex_control_id, 
                                'complex_count':complex_count, 
                                'complex_max':complex_max }) # ,'controls':lines


            if card_id == previous_card_id:
                device_id += 1
            
            previous_card_id = card_id

    return audio_controls



def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = None
    finally:
        s.close()
    return IP



def valid_ip(ip):
    return ip.count('.') == 3 and \
        all(0 <= int(num) < 256 for num in ip.rstrip().split('.')) and \
        len(ip) < 16 and \
        all(num.isdigit() for num in ip.rstrip().split('.'))
        
        
def generate_random_string(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))





#
#  A quick scan of the network.
#
def arpa_detect_gateways(quick=True):
    command = "arp -a"
    gateway_list = []
    try:
        
        s = requests.Session()
        s.mount('http://', HTTPAdapter(max_retries=0))
        s.mount('https://', HTTPAdapter(max_retries=0))
        
        result = subprocess.run(command, shell=True, universal_newlines=True, stdout=subprocess.PIPE) #.decode())
        for line in result.stdout.split('\n'):
            #print(str(line))
            if len(line) > 10:
                
                if quick and "<incomplete>" in line:
                    #print("skipping incomplete ip")
                    continue
                    
                #print("--useable")
                #name = "?"

                try:
                    ip_address_list = re.findall(r'(?:\d{1,3}\.)+(?:\d{1,3})', str(line))
                    #print("ip_address_list = " + str(ip_address_list))
                    ip_address = str(ip_address_list[0])
                    if not valid_ip(ip_address):
                        continue
                        
                    #print("found valid IP address: " + str(ip_address))
                    try:
                        test_url_a = 'http://' + str(ip_address) + "/"
                        test_url_b = 'https://' + str(ip_address) + "/"
                        html = ""
                        try:
                            response = s.get(test_url_a, allow_redirects=True, timeout=1)
                            #print("http response: " + str(response.content.decode('utf-8')))
                            html += response.content.decode('utf-8').lower()
                        except Exception as ex:
                            #print("Error scanning network for gateway using http: " + str(ex))
                            
                            
                            try:
                                response = s.get(test_url_b, allow_redirects=True, timeout=1)
                                #print("https response: " + str(response.content.decode('utf-8')))
                                html += response.content.decode('utf-8').lower()
                            except Exception as ex:
                                #print("Error scanning network for gateway using https: " + str(ex))
                                pass
                            
                        if 'webthings' in html:
                            #print("arp: WebThings controller spotted at: " + str(ip_address))
                            #print(str(response.content.decode('utf-8')))
                            if ip_address not in gateway_list:
                                gateway_list.append(ip_address) #[ip_address] = "option"
                    
                    except Exception as ex:
                        print("Error: could not analyse IP from arp -a line: " + str(ex))
                        
                except Exception as ex:
                    print("no IP address in line: " + str(ex))
                    
               
                
    except Exception as ex:
        print("Arp -a error: " + str(ex))
        
    return gateway_list