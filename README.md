# Crossword generator
Generates crosswords and exports them to htlm, png or ascii

# Thanks 
to Bryan Helmig for his inspiration for this script. He did a lot of work which 
I could improve in some ways.
See http://bryanhelmig.com/python-crossword-puzzle-generator/ for his code.


# License
GPLv3

# Speed up the script
Use PyPy oder Psyco to speed up the script

# Font 
To get the output font working on Ubuntu: 

1. use apt-get to install package `ttf-mscorefonts-installer`
2. edit `crossword.py` to have the correct path to `arial.ttf`
