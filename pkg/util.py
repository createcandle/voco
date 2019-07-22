"""Utility functions."""

def pretty(d, indent=0):
    for key, value in d.items():
        print('\t' * indent + str(key))
        if isinstance(value, dict):
            pretty(value, indent+1)
        else:
            print('\t' * (indent+1) + str(value))
            
def is_a_number(s):
    """ Returns True is string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        return False
    
def make_safe_name(s):
    keepcharacters = (' ','.','_')
    return "".join(c for c in s if c.isalpha() or c.isalnum() or c in keepcharacters).rstrip()

    
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

