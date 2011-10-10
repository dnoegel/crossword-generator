#!/usr/bin/env pypy
# coding:utf-8

# ----------------------------------------------------------------------------
# crossword - Simple Crossword generator in Python
# Copyright (c) 2011 Daniel Nögel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------------

import os
import glob
import sys
import random
import re
import time
import string
import copy
import Image, ImageDraw, ImageFont
from optparse import OptionParser, OptionGroup
import logging

## Thanks Bryan Helmig for his inspiration for this script. He did a lot
# of work which I could improve in some ways.
# See http://bryanhelmig.com/python-crossword-puzzle-generator/ for his
# code.

## With Bryan's permission this code is released under GPLv3
 
# optional, speeds up by a factor of 4
try:
    if not "--nopsyco" in sys.argv:
        import psyco
        psyco.full()
except ImportError, inst:
    print("Psyco not available: '%s'" % inst)
    print("Using PsyCo will speed up this script up to factor 8")
    print("Using PyPy will also speed up your script")

## Define some Exceptions
class SolutionError(Exception):
    pass
class TimeOutError(Exception):
    pass
class WordListError(Exception):
    pass
class MaxLoopError(Exception):
    pass

def stats(cwd, print_missing=True):
    """Print some infos about a given crossword."""
    
    ## How many words have been placed?
    print(len(cwd.placed_words), 'out of', len(cwd.wordlist))
    
    ## Which words couldn't be placed?
    if print_missing:
        tmplist = [w.word.lower() for w in cwd.placed_words]
        missing = [w.word for w in cwd.wordlist if w.word.lower() not in tmplist]
        print("Missing words: '%s'" % missing)
    
    ## Number of rounds (--)
    print("Needed %i rounds" % cwd.counter)
    
    ## average number of crosses per word
    score = float(cwd.score)
    print("%f crosses per word" % (float(score-len(cwd.placed_words))/len(cwd.placed_words)))
    
    ## Empty and filled cells / Empty-cell-quotient
    num_cells = float(cwd.cols * cwd.rows)
    num_letters = sum(w.length for w in cwd.placed_words)
    num_empty = num_cells - num_letters
    print("total-cells/empty-cells- Quotient: %.1f/1 (%i, %i)" % (round(num_cells/num_empty, 1), num_cells, num_empty))

def run_benchmark_test(words=100, num=100, bestof=3):
    """Generate a lot of crosswords"""
    
    print("\nWill create %i crosswords, each best of %i." % (num, bestof))
    print("So %i crosswords will be generated." % (num*bestof))
    print("Each crossword will have %i words\n" % words)
    
    start = time.time()
    
    #~ parser = SimpleParser("weimar.cwf")
    #~ word_list = parser.get_questions()
    #~ print word_list
    #~ print word_list
    #~ raw_input()
    curdir = os.path.dirname(sys.argv[0])
    curdir = os.path.abspath(curdir)
    db = SimpleParser(os.path.join(curdir, "crosswords", "lot_questions.cwf"))
    word_list = db.get_questions(words)
    best_score, best_crossword = 0, None
    cwds = multiple_crosswords("auto","auto", " ", 5000, word_list, num=num, best_of=bestof, force_solved=False)
    for cwd, score in cwds:
        if score >= best_score:
            best_score = score
            best_crossword = cwd
    print(70*"=")    
    print("Best Crossword with %i points:" % best_score)
    formatter = CrossWordFormatter(best_crossword, ppb=32)#, solution="I solved it")
    #~ print formatter.get_crossword_ascii_grid(solved=False, printable=True)
    print formatter.get_crossword_ascii_grid(solved=True, printable=True)
    #~ print formatter.get_crossword_ascii_cues()
    #~ print formatter.get_shuffled_word_list()
    formatter.get_crossword_image_grid(output="benchmark-output-file.png", solved=True)
    #~ formatter.get_crossword_html_grid(   )
    stats(best_crossword)
    #~ print [i.word for i in best_crossword.wordlist]
    #~ print [i.word for i in best_crossword.placed_words]
    end = time.time()
    
    msg = "= This benchmark took %.4f seconds =" % (end-start)
    print(len(msg)*"=")
    print(msg)
    print(len(msg)*"=")

class SimpleParser(object):
    """A simple parser for .cwf files
    
    Actually it's a veeeeeery simple .ini parser. But it ignores letter-cases
    which most other parser do not.
    """
    
    def __init__(self, filename=None):
        self.dict = {}
        if filename:
            self.parse(filename)
            
    def get_questions(self, num=None):
        """Returns a list of (answer, question) tuples
        
        --num Number of questions. Default: None = All
        """
        
        if num is None or num == 0: 
            return self.dict["questions"]
        else:
            return self.dict["questions"][:num]
        
    def get_option(self, option):
        """Get the value of a given options from the options-section"""
        
        return self.dict["options"][option]
        
    def has_option(self, option):
        """True/False depending on if the given options exists or not"""
        
        return option in self.dict["options"]
    
    def parse(self, filename):
        """Parse the given file"""
        
        section = None
                
        with open(filename, "r") as fh:
            #~ content = [line.replace() for line in fh]
            content = fh.read().split("\n")
        
        ## First pass: Just get the sections and options!
        for line in content:
            rg = re.match(r"\s*\[(\w.*)\]", line) ## Matches a section
            if rg:
                # Set current section
                section = rg.group(1).strip().lower()
                if not section in self.dict and section == "options":
                    self.dict[section] = {}
                elif not section in self.dict:
                    self.dict[section] = []
            elif re.match(r"\A\s*\Z", line):
                # Ignore blank lines
                pass
            elif section == "options":
                rg = re.match(r"\s*(?P<key>.+?)[ \t]*?[:=][ \t]*(?P<value>.+)", line) # Match key = value
                if rg:
                    if rg.group("key").strip().lower() == "question first":
                        self.dict[section]["question first"] = rg.group("value").lower().strip().startswith("t")
                    else:
                        self.dict[section][rg.group("key").strip().lower()] = rg.group("value").strip()
        
        if not "options" in self.dict:
            self.dict["options"] = {}
                        
        if not "question first" in self.dict["options"]: self.dict["options"]["question first"] = True
        
        ## Second pass: Get the questions
        section = None
        for line in content:
            rg = re.match(r" *\[(\w.*)\]", line)
            if rg:
                # Set current section
                section = rg.group(1).strip().lower()
            elif re.match(r"\A\s*\Z", line):
                # Ignore blank lines
                pass
            #~ elif section == None:
                #~ pass
            elif section != "options":
                rg = re.match(r"\s*(?P<key>.+?)[ \t]*?[:=][ \t]*(?P<value>.+)", line)
                if rg:
                    if self.dict["options"]["question first"]:
                        self.dict[section].append((rg.group("value").strip(), rg.group("key").strip()))
                    else:
                        self.dict[section].append((rg.group("key").strip(), rg.group("value").strip()))

 
class CrossWordFormatter(object):
    """Formatting Crosswords
    
    This class manages the various ways of crossword-output. Do you want
    it as html, image, text, solved or unsolved?"""
    
    def __init__(self, crossword, ppb=32, solution=None, transparency=False, order=True):
        """-- ppb Pixel per box (Default: 32)
        -- solution A string representing the solution (e.g. "Hallo"). 
        Each letter of that string will be marked on the crossword grid
        as an colored field
        -- transparency Should the image bg be transparend?
        -- order
        """
        
        self.crossword = crossword
        self.ppb = ppb

        if order:
            self.crossword._number_words()
    
        self.solution_letters = {}
        if solution:
            self._set_solution(solution.lower())
        else:
            self.solution=None
        
        if transparency:
            transp = 0
        else:
            transp = 255
        
        self.colors = {}
        self.colors["bg"] = (255,255,255, transp)
        self.colors["grid"] = (0,0,0)
        self.colors["bg-box"] = (255,255,255)
        self.colors["shadow-grid"] = (100,100,100)
        self.colors["highlight"] = None
        self.colors["text"] = (0,0,0)
        
        self.highlight_colors = [(80, 73, 158, 128), (75, 191, 84, 128), (219, 61, 101, 128), (237, 230, 36, 128), (132, 215, 240, 128)]
    
    ## obsolet
    def _next_highlight_color(self):
        self.current_highlight_color += 1
        try:
            self.colors["highlight"] = self.highlight_colors[self.current_highlight_color]
        except IndexError:
            print("Generating random highlight color - please add additional highlight colors")
            self.colors["highlight"] = (random.randint(0,255),random.randint(0,255),random.randint(0,255), 128)

    def get_crossword_html_grid(self, filename):
        """Writes an html file
        
        todo: Add solved-switch
        """


        for word in self.crossword.placed_words:
            self.crossword._write_cell(word.col, word.row, word.number)
        
        
        html = """<html>
        <head>
        <style type="text/css">
        ;table { width:100%; }
        td { border-spacing: 2px 2px;border:0px solid #000; vertical-align:middle; text-align:center; width:15; height:15; }
        #box { border:1px solid #000; vertical-align:middle; text-align:center; width:15; height:15; }
        </style>
        </head>
        <body>"""
                
            
        html += "<table>"
        for row in range(self.crossword.rows):
            html += "<tr>"
            for cell in self.crossword.grid[row]:
                if isinstance(cell, int):
                    html += "<td id=\"box\"><small>%s</small></td>" % cell
                elif cell == self.crossword.empty:
                    html += "<td>%s</td>" % cell
                else :
                    html += "<td id=\"box\"><small>&nbsp;</small></td>" 
            html += "</tr>"
        html += "</table></body></html>"

        for word in self.crossword.placed_words:
            self.crossword._write_cell(word.col, word.row, word.word[0])

        with open(filename, "w") as fh:
            fh.write(html)     
        return html
    
    def _set_solution(self, solution):
        """Checks if enough letters are available for the given solution
        and put those letters into an list"""
        #~ for letter in self.crossword.letters:
            #~ print letter, [self.crossword._read_cell(col, row) for col, row in self.crossword.letters[letter]]
        #~ 
        #~ return
        
        highlight_color_number = 0
        
        while "  " in solution:
            solution = solution.replace("  ", " ")
        
        self.solution = solution
        
        for letter in solution:
            if letter == " ":
                highlight_color_number += 1
                continue
            if not letter in self.crossword.letters or self.crossword.letters[letter] == []:
                raise SolutionError("Cannot mark solution-letter '%s': No '%s' in this crossword" % (letter, letter))
            if solution.count(letter) > len(self.crossword.letters[letter]):
                raise SolutionError("Your solution '%(solution)s' has %(num)i '%(letter)s' - there are not that much '%(letter)s's in your crosssword!" % {"num":solution.count(letter), "letter":letter, "solution":solution})
            
            entry = random.choice(self.crossword.letters[letter])
            while entry in self.solution_letters:
                entry = random.choice(self.crossword.letters[letter])
                
            self.solution_letters[entry] = highlight_color_number
            col,row = entry

    def get_wordfind_ascii_grid(self, printable): 
        """Returns a word-find ascii grid"""
        
        if printable: 
            printstr  = " "
        else:
            printstr = ""
        
        outStr = ""
        for r in range(self.crossword.rows):
            for c in self.crossword.grid[r]:
                if c == self.crossword.empty:
                    outStr += '%s%s' % (string.lowercase[random.randint(0,len(string.lowercase)-1)], printstr)
                else:
                    outStr += '%s%s' % (c, printstr)
            outStr += '\n'
        return outStr

    def get_shuffled_word_list(self): 
        """Returns a string of (shuffled) words (solutions)"""
        
        outStr = ''
        tmplist = copy.duplicate(self.crossword.placed_words)
        random.shuffle(tmplist) # randomize word list
        for word in tmplist:
            outStr += '%s\n' % word.word
        return outStr


    def get_crossword_ascii_cues(self): 
        """Returns the crossword's questions"""
        
        across_str = "Across:\n"
        down_str = "Down:\n"
        
        for word in self.crossword.placed_words:
            if word.vertical:
                down_str += "%d: %s\n" % (word.number, word.clue)
                
            else:
                across_str += "%d: %s\n" % (word.number, word.clue)
        
        return "%s\n\n%s" % (across_str, down_str)

    def get_crossword_ascii_grid(self, solved = False, printable=False):
        """Returns a crossword grid with numbers"""

        if printable: 
            printstr  = " "
        else:
            printstr = ""

        outStr = ""
 
 
        if not solved: 
            for word in self.crossword.placed_words:
                self.crossword._write_cell(word.col, word.row, word.number)
 
        for r in range(self.crossword.rows):
            for c in self.crossword.grid[r]:
                outStr += '%s%s' % (c, printstr)
            outStr += '\n'
            
        if not solved:
            for word in self.crossword.placed_words:
                self.crossword._write_cell(word.col, word.row, word.word[0])
 
        if not solved:
            outStr = re.sub(r'[a-z]', '_', outStr)
        return outStr
        
    def get_crossword_image_grid(self, output, solved=False):
        """Draw an image"""
        
        ppb = self.ppb
        num_offset = 2
        shadow_depth= ppb*0.25
        
        font = ImageFont.truetype("/usr/share/fonts/TTF/arial.ttf", int(ppb/1.5))
        number_font = ImageFont.truetype("/usr/share/fonts/TTF/arial.ttf", int(ppb/3))
        
        if self.solution:
            width, height = self.crossword.cols*ppb, self.crossword.rows*ppb
            height += 2*ppb
            if len(self.solution)*ppb > width:
                width = len(self.solution)*ppb
        else:
            width, height = self.crossword.cols*ppb, self.crossword.rows*ppb
        img = Image.new("RGBA", (width, height), self.colors["bg"])
        draw = ImageDraw.ImageDraw(img)
        #~ draw.rectangle([(0, 0), (self.crossword.rows*self.ppb, self.crossword.cols*self.ppb)], fill="white")
        
        ## Solution-box coords:
        if self.solution:
            solution_len = len(self.solution)*ppb
            start_x = width/2 - solution_len/2
            start_y = height - ppb
            #~ solution_coords = [(x, start_y) for x in xrange(start_x, start_x+solution_len, ppb)]
            #~ solution_coords = [(x, start_y//ppb) for x in xrange(start_x//ppb, (start_x//ppb)+(solution_len//ppb))]
            c =  0
            solution_coords = []
            for letter in self.solution:
            #~ for x in xrange(start_x//ppb, (start_x//ppb)+(solution_len//ppb)):
                if letter == " ":
                    solution_coords.append((None, None))
                else:
                    solution_coords.append((start_x//ppb + c, start_y//ppb))
                c += 1
        
        ## ---------
        ## Draw shadow
        ppb = self.ppb
        for letter in self.crossword.letters:
            for col, row in self.crossword.letters[letter]:
                col -= 1
                row -= 1
                draw.polygon([col*ppb,row*ppb, col*ppb+shadow_depth, row*ppb-shadow_depth, (col+1)*ppb+shadow_depth, row*ppb-shadow_depth, (col+1)*ppb+shadow_depth, (row+1)*ppb-shadow_depth, (col+1)*ppb, (row+1)*ppb, col*ppb, (row+1)*ppb, col*ppb, row*ppb], fill=self.colors["shadow-grid"], outline=self.colors["shadow-grid"])
                #~ draw.rectangle([col*self.ppb, row*self.ppb-3, (col+1)*self.ppb+3, (row+1)*self.ppb], fill=self.colors["shadow-grid"], outline=self.colors["shadow-grid"])
        if self.solution:
            for col, row in solution_coords:
                if col and row:
                    col -= 1
                    row -= 1
                    draw.polygon([col*ppb,row*ppb, col*ppb+shadow_depth, row*ppb-shadow_depth, (col+1)*ppb+shadow_depth, row*ppb-shadow_depth, (col+1)*ppb+shadow_depth, (row+1)*ppb-shadow_depth, (col+1)*ppb, (row+1)*ppb, col*ppb, (row+1)*ppb, col*ppb, row*ppb], fill=self.colors["shadow-grid"], outline=self.colors["shadow-grid"])

        ## ---------
        ## Draw grid
        for col in range(self.crossword.cols):
            row = 0
            for cell in self.crossword.grid[col]:
                if not cell == self.crossword.empty:
                    if (col+1, row+1) in self.solution_letters:
                        fill_color = self.highlight_colors[self.solution_letters[(col+1, row+1)]] 
                        #self.colors["highlight"]
                    else:
                        fill_color = self.colors["bg-box"]
                    draw.rectangle([col*self.ppb, row*self.ppb, (col+1)*self.ppb, (row+1)*self.ppb], outline=self.colors["grid"], fill=fill_color)
                row += 1
        if self.solution:
            highlight_color = 0
            for col, row in solution_coords:
                if col and row:
                    col -= 1
                    row -= 1
                    fill_color = self.highlight_colors[highlight_color] 
                    draw.rectangle([col*self.ppb, row*self.ppb, (col+1)*self.ppb, (row+1)*self.ppb], outline=self.colors["grid"], fill=fill_color)
                else:
                    highlight_color += 1

        ## ---------
        ## Draw numbers and letters
        self.blocked_fields = []
        for word in self.crossword.placed_words:
            col, row = word.col, word.row
                       
            if solved:
                letter_counter = 0
                for letter in word.word:
                    w, h = draw.textsize(letter, font=font)
                    letter_offset_x = self.ppb/2 - w/2
                    letter_offset_y = self.ppb/2 - h/2
                    if word.vertical:
                        draw.text(((col-1)*self.ppb+letter_offset_x, (row-1+letter_counter)*self.ppb+letter_offset_y), str(letter), fill="black", font=font)
                    else:
                        draw.text(((col-1+letter_counter)*self.ppb+letter_offset_x, (row-1)*self.ppb+letter_offset_y), str(letter), fill="black", font=font)
                    letter_counter+=1
            
            if (col, row) in self.blocked_fields:
                dummy, y_offset = draw.textsize("123456789", font=number_font)
            else:
                y_offset = 0
            draw.text(((col-1)*self.ppb+num_offset, (row-1)*self.ppb+num_offset+y_offset), str(word.number), fill=self.colors["text"], font=number_font)
            w, h = draw.textsize(str(word.number), font=number_font)
            #~ w = w/len(str(word.number))
            if word.vertical:
                self._draw_arrow(draw, "down", (col-1)*self.ppb+num_offset+w, (row-1)*self.ppb+num_offset+y_offset, w/len(str(word.number)), h)
            else:
                self._draw_arrow(draw, "right", (col-1)*self.ppb+num_offset+w, (row-1)*self.ppb+num_offset+y_offset, w/len(str(word.number)), h)
            
            self.blocked_fields.append((col, row))
            
        ## ----------
        ## Draw Solution
        if solved and self.solution:
            for letter in self.solution[::-1]:
                w, h = draw.textsize(letter, font=font)
                letter_offset_x = self.ppb/2 - w/2
                letter_offset_y = self.ppb/2 - h/2
                
                col, row = solution_coords.pop()
                if col and row:
                    draw.text(((col-1)*self.ppb+letter_offset_x, (row-1)*self.ppb+letter_offset_y), letter, fill="black", font=font)

        img.save(output, "PNG")
    
    def _draw_arrow(self, draw, dir, x, y, w, h):
        if dir == "right":
            draw.line([x, y+h//2, x+w, y+h//2], fill="black")
            draw.line([x+w, y+h//2, x+w-w/2, y+h//2-h/3], fill="black")
            draw.line([x+w, y+h//2, x+w-w/2, y+h//2+h/3], fill="black")
        elif dir == "down":
            draw.line([x+w//2, y, x+w//2, y+h], fill="black")
            draw.line([x+w//2, y+h, x+w/2-w/3, y+h-h/2], fill="black")
            draw.line([x+w//2, y+h, x+w/2+w/3, y+h-h/2], fill="black")
        else:
            raise Exception("What the... ? I just can draw right and down arrows!")


def wordlist_from_string(str, get_crossword_solution_delimiter="/", question_delimiter="\n", get_crossword_solution_first=True):
    """Creates a wordlist from a string."""
    
    lines = str.split(question_delimiter)
    
    wordlist = []
    
    for line in lines:
        if get_crossword_solution_first:
            get_crossword_solution, question = line.split(get_crossword_solution_delimiter)
        else:
            question, get_crossword_solution = line.split(get_crossword_solution_delimiter)
            
        wordlist.append((get_crossword_solution, question))
    
    return wordlist
    
def multiple_crosswords(cols, rows, empty = "-", maxloops=2000, wordlist=[], num=10, time_permitted=2.0, best_of=10, force_solved=False):
    """Creates a lot of crosswords.
    
    First this was a common function that sorted the crosswords by score 
    and returned them in a list.
    Now this is a generator return a tuple (crossword, score). You have
    to do the sorting by your own."""
    crosswords = []
    
    for i in range(0,num):
        cross = CrossWord(cols, rows, empty, maxloops, wordlist)
        score = cross.compute_crossword(best_of=best_of, force_solved=force_solved)
        crosswords.append((cross, score))
        yield cross, score
    #~ 
    #~ ## Sort by score
    #~ crosswords.sort(key=lambda i: i[1], reverse=True) # sort by score
    #~ return crosswords[0]

class CrossWord(object):
    """The crossword objects represents a crossword"""

    def __init__(self, cols, rows, empty = '_', maxloops = 2000, wordlist=[], reduce=None):       
        """Initialize the crossword. Notice: This will also be used to create
        a copy of the original crossword. For this reason there is some
        wordlist-"magic" in here."""
        
        if len(wordlist) < 3:
            raise WordListError("Need at least 3 entries!")

        if cols =="auto" or rows == "auto":
            if wordlist != [] and isinstance(wordlist[0], tuple):
                longest = max(wordlist, key=lambda i: len(i[0]))[0]
                average = sum([len(w[0]) for w in wordlist])/len(wordlist)
            #~ elif isinstance(wordlist[0], str):
                #~ longest = max(wordlist, key=lambda i: len(i))
                #~ average = sum(wordlist)/len(wordlist)
            elif wordlist != []:
                print type(wordlist[0])
                raise WordListError("Wordlist must contain strings or tuples!")
            min_length = len(longest)
            #~ if not reduce:
            logging.debug("'%s': %i - Average: %i" % (longest, min_length, average))
        
            size = int(((average*len(wordlist)*4)**0.5))
            if len(wordlist) > 75:
                size = int(size*0.8)
            #~ if reduce:
                #~ size = int(size*reduce)
            while size <= min_length:
                size += 1
                
        if cols == "auto":
            cols = size
        if rows == "auto":
            rows = size
        logging.debug("Grid size: %ix%i" % (cols, rows))
        
        self.cols = cols
        self.rows = rows
        self.empty = empty
        self.maxloops = maxloops
        self.wordlist = wordlist
        self.placed_words = []
        self.counter = 0
        self._setup_grid_and_letters()
        
        self.score = -1
        
    def _setup_grid_and_letters(self):
        """Initialize / clear grid and letters"""
        
        ## Create the grid and fill it with empty letters
        self.grid = []
        for i in range(self.cols):
            col = []
            for j in range(self.rows):
                col.append(self.empty)
            self.grid.append(col)
        
        ## Create our letter-dict
        self.letters = {}
        for letter in string.lowercase: self.letters[letter]=[]
        ## In "double" we'll put those coords which already are used
        # by two words (cross). So we do not check coords, that are already
        # occupied.
        self.letters["double"]=[]
        
        ## Sort the wordlist by length. Words with same length will be
        # shuffled in order.
        tmplist = []
        for word in self.wordlist:
            if isinstance(word, Word):
                tmplist.append(Word(word.word, word.clue))
            else:
                tmplist.append(Word(word[0], word[1]))
        random.shuffle(tmplist)
        tmplist.sort(key=lambda i: len(i.word), reverse=True)
        self.wordlist = tmplist
 
    def compute_crossword(self, rounds=2, best_of=3, force_solved=False):
        """Compute possible crosswords
        
        -- rounds: How often sould be tried to place a word? (Default: 2)
        -- best_of: Creates the given number of crosswords and keeps the 
            crossword with the best score (Default: 3)
        -- force_solved Generate grids until every word from the wordlists
            fits. (Default: False).
        """
        
        copy = CrossWord(self.cols, self.rows, self.empty, self.maxloops, [(w.word, w.clue) for w in self.wordlist], reduce=reduce)
        
        best_score = 0
        count = 0

        solved = False
 
        while (count<=best_of-1 and not force_solved) or (force_solved and not solved):
            self.counter += 1
            logging.debug("Round %i" % count)

            score = 0
            copy.placed_words = []
            copy._setup_grid_and_letters()

            ## Try to fit all the words from the wordlist onto the grid
            x = 1
            while x < rounds:
                for word in copy.wordlist:
                    if word not in copy.placed_words:
                        #~ raw_input()
                        word_score = copy._place_word(word)
                        score += word_score
                x += 1

            ## Check if the copy-crossword is "better" than the original. 
            if (len(copy.placed_words) >= len(self.placed_words) and score >= best_score) or len(copy.placed_words) > len(self.placed_words):
                self.placed_words = copy.placed_words
                self.wordlist = copy.wordlist
                self.grid = copy.grid
                self.letters = copy.letters
                self.cols = copy.cols
                self.rows = copy.rows
                best_score = score
            
            ## If all words are on the list the crossword ist "solved"
            if len(copy.placed_words) == len(copy.wordlist):
                solved = True
            else:
                solved = False
                
            count += 1
            
            if force_solved and count >= self.maxloops:
                raise MaxLoopError("Could not solve the crossword within %i tries" % self.maxloops)
        
        self.score = best_score
        return best_score
 
    def _get_possible_coords(self, word):
        """Generates a list of possible coords.
        
        Any cell containing a letter of the world will be saved as a possible hit
        if the word would fit at that position without leaving the grid-bounds.
        Additional checking is done later.
        """

        coordlist = []
        
        ## optimizations
        letters = self.letters
        cols = self.cols
        rows = self.rows
        word_str = word.word
        word_length = len(word_str)
        _get_score = self._get_score
        
        letterpos = -1
        #~ for letterpos, letter in enumerate(word.word): ## Enumerate seems to be slower sometimes
        for letter in word_str:
            letterpos += 1
            
            try:
                coords = letters[letter]
            except KeyError:
                coords = []
            
            for col, row in coords:
                ## VERTICAL
                if row - letterpos > 0: 
                    if ((row - letterpos) + word_length) <= rows: 
                        score = _get_score(col, row - letterpos, 1, word)
                        if score:
                            coordlist.append((col, row - letterpos, 1, score))
                
                ## HORIZONTAL
                if col - letterpos > 0:
                    if ((col - letterpos) + word_length) <= cols: 
                        score = _get_score(col - letterpos, row, 0, word)
                        if score:
                            coordlist.append((col - letterpos, row, 0, score))
            
        ## The same trick as in the '_randomize_wordlist' methode:
        # The list needs to be sorted (this time by score) but coords
        # with the same score may be shuffled and will lead to 
        # different crosswords each time.
        random.shuffle(coordlist)
        coordlist.sort(key=lambda i: i[3], reverse=True)
        return coordlist
         
    def _place_word(self, word): 
        """Put a word onto the grid.
        
        The first word will be put at random coords, the following words
        will be placed by match-score."""
    
        placed = False
        count = 0
        score = 0
 
        if len(self.placed_words) == 0: 
            while not placed and count <= self.maxloops:
                ## Place the first word at fixed coords
                vertical, col, row = random.randrange(0, 2), 1, 1
                
                ## Place the first word in the middle of the grid
                if vertical:
                    col = int(round((self.cols + 1) / 2, 0))
                    row = int(round((self.rows + 1) / 2, 0)) - int(round((len(word.word) + 1) / 2, 0))
                    if row+len(word.word) > self.rows:
                        row = self.rows - len(word.word) + 1
                else:
                    col = int(round((self.cols + 1) / 2, 0)) - int(round((len(word.word) + 1) / 2, 0))
                    row = int(round((self.rows + 1) / 2, 0))
                    if col+len(word.word) > self.cols:
                        col = self.cols - len(word.word) + 1

                ## Random place the first word
                #~ col = random.randrange(1, self.cols + 1)
                #~ row = random.randrange(1, self.rows + 1)
                
                if self._get_score(col, row, vertical, word): 
                    placed = True
                    self._write_word(col, row, vertical, word)
                    return 0
                count += 1
        else:
            coordlist = self._get_possible_coords(word)
            try: 
                col, row, vertical, fit_score = coordlist[0]
            except IndexError: 
                ## If there are no coords, don't place the word and
                ## return 0 (score)
                return 0

            score += fit_score
            self._write_word(col, row, vertical, word)
            
        if count >= self.maxloops:
            raise MaxLoopError("Maxloops reached - canceling (Counter: %i, Word: %s)" % (count, word.word))
 
        return score
 
    def _get_score(self, col, row, vertical, word):
        """Calculate the placement-score of a word for the given coords
        
        Return:
        -- 0 No coord fits
        -- 1 coord fits - but no cross
        -- n n-1 crosses"""
        
        ## optimizations
        empty = self.empty
        _is_empty = self._is_empty
        _read_cell = self._read_cell
        grid = self.grid
        #~ def _is_empty(col, row):
            #~ try: 
                #~ return grid[col-1][row-1] == empty
            #~ except IndexError:
                #~ pass
            #~ return False
        
        if col < 1 or row < 1:
            return 0
 
        score = 1
        letterpos = 0
        lastletter = empty
        
        #~ for letterpos, letter in enumerate(word.word):   ## Enumerate is much(!) slower
        for letter in word.word:
            letterpos += 1
            
            try:
                active_cell = grid[col-1][row-1]#_read_cell(col, row)
            except IndexError:
                return 0
            
            ## Still not ideal, but this prevents the code from placing
            # a word like "nose" over an already placed word like "nosebear"!
            # This is quite a big issue - so this part really should kept.  
            #
            # Another approach would be, to check for each cell if it
            # already contains a letter, which is written in the same
            # direction as our word. e.g.:
            # The active_cell holds an 'e', also our word has an 'e'.
            # If the 'e' of the active_cell belongs to a vertical word 
            # and our word is also going to be placed vertically, a match
            # is not possible as we would overwrite the old world.
            # If the active_cell belongs to a horizontal word, a cross
            # would be possible. The downside of this approach: We'd
            # need an additional dict/list for that info, it would be slower
            if lastletter != empty and active_cell != empty:
                return 0
            lastletter = active_cell
            
            ## In words: If the letter of the current cell does not
            # match the current letter of our word, the word doesn't
            # fit!
            if active_cell != empty and active_cell != letter:
            #~ if active_cell != empty and letterpos != matching_letter:    ## This will disallow words to be overwritten but it will also disallow multiple matches within one word
                return 0
            elif active_cell == letter:
                score += 1
            
            
            #
            # Check for neighbours
            #
            if vertical:
                ## Only check for non-crosses
                if active_cell != letter: 
                    # right
                    if not _is_empty(col+1, row): 
                        return 0
 
                    # left
                    if not _is_empty(col-1, row): 
                        return 0
 
 
                ## Only check first and last letter in vertical mode
                # for top/bottom neighbours. 
                if letterpos == 1: 
                    if not _is_empty(col, row-1):
                        return 0
 
                if letterpos == len(word.word): 
                    if not _is_empty(col, row+1): 
                        return 0
            else: 
                ## Only check for non-crosses
                if active_cell != letter:
                    # top
                    if not _is_empty(col, row-1): 
                        return 0
 
                    # bottom
                    if not _is_empty(col, row+1): 
                        return 0
 
                ## In horizontal mode only the first and last letter
                # are not allowed to have horizontal neighours
                if letterpos == 1: 
                    if not _is_empty(col-1, row):
                        return 0
 
                if letterpos == len(word.word): 
                    if not _is_empty(col+1, row):
                        return 0

            if vertical: 
                row += 1
            else: 
                col += 1
 
        return score
 
    def _write_word(self, col, row, vertical, word): 
        """Write a word to the grid and add it to the placed_words list"""
        
        word.col = col
        word.row = row
        word.vertical = vertical
        #~ if word.word in self.placed_words:
            #~ raise Exception("Word '%s' two times in the crossword!!" % word)

        self.placed_words.append(word)

        for letter in word.word:
            #~ self.cells.append((col, row, vertical))
                
            self._write_cell(col, row, letter)
            if vertical:
                row += 1
            else:
                col += 1
        return
 
    def _write_cell(self, col, row, letter):
        """Set a cell on the grid to a given letter"""
        
        try:
            if not (col, row) in self.letters[letter]:
                self.letters[letter].append((col, row)) 
            else:
                ## Remove coords from the list, if they already
                # contain a cross. This way we do less double-checking.
                self.letters[letter].remove((col, row)) 
                self.letters["double"].append((col, row)) 
        except KeyError:
            self.letters[letter] = []
            self.letters[letter].append((col, row))
        
        self.grid[col-1][row-1] = letter
        
    def _read_cell(self, col, row):
        """Get the content of a cell"""
        
        return self.grid[col-1][row-1]
 
    def _is_empty(self, col, row):
        """Check if a given cell is empty"""
        
        try:
            return self.grid[col-1][row-1] == self.empty
        except IndexError:
            pass
        return False

    def _number_words(self): 
        """Orders the words and applies numbers to them
        
        Words starting at the same cell will get the same number (e.g.
        'ask' and 'air' would become 1-across and 1-down.)
        """
    
        self.placed_words.sort(key=lambda i: (i.col + i.row))
        
        
        across_count, down_count = 1, 1
        
        ignore_num = []
        
        for word in self.placed_words:
            if word.number == None:
                if word.vertical:
                    while across_count in ignore_num:
                        across_count +=1
                    word.number = across_count
                    across_count +=1
                else:
                    while down_count in ignore_num:
                        down_count +=1
                    word.number = down_count
                    down_count +=1
                    
                ## Check if any other word starts at the same coords
                # in that case apply the same number to that word
                for word2 in self.placed_words:
                    if word2.col == word.col and word2.row == word.row and word2 is not word:
                        word2.number = word.number
                        ignore_num.append(word.number)

class Word(object):
    def __init__(self, word=None, clue=None):
        self.word = re.sub(r'\s', '', word.lower())
        self.clue = clue
        self.length = len(word) ## Much faster than asking for len(word)

        self.row = None
        self.col = None
        self.vertical = None
        self.number = None
        
        ## Used if the word is a solution-field (colored)
        self.solution = False
        self.solution_char = None
    
    def __len__(self):
        print("Please use len(word.word) to ask for the length of the word - this is much faster")
        return len(self.word)
    
    #~ def __getitem__(self, item):
        #~ if item == 0:
            #~ return self.word
        #~ elif item == 1:
            #~ return self.clue
        #~ else:
            #~ raise KeyError

if __name__ == "__main__":
    parser = OptionParser()
    general_group = OptionGroup(parser, "General Options")
    general_group.add_option("--nopsyco", help="Do not import psyco", dest="nopsyco", default=False, action="store_true")
    general_group.add_option("--benchmark", help="Run a benchmark-test", dest="benchmark", default=None, action="store_true")
    general_group.add_option("--benchmark-settings", help="Format: 'x,y,z' x=Number of words on each crossword, y=Number of crosswords to generate, z=Each crossword should be the best of ...?", dest="bsettings", default="100,100,3", action="store")
    general_group.add_option("--stats", help="Print stats", dest="stats", default=None, action="store_true")
    parser.add_option_group(general_group)
    
    crossword_group = OptionGroup(parser, "Crossword Options")
    crossword_group.add_option("-c", "--cols", help="Number of columns to use (Default: auto)", dest="columns", default="auto", action="store")
    crossword_group.add_option("-r", "--rows", help="Number of rows to use (Default: auto)", dest="rows", default="auto", action="store")
    crossword_group.add_option("-s", "--solution", help="The crossword's solution (some colored fields which letters can be used to build a word).\nNote: This will overwrite any solution defined in the input file(s)!! ", action="store", dest="solution", default=None)
    crossword_group.add_option("--solved", help="Create a solved crossword", action="store_true", dest="solved", default = False)
    crossword_group.add_option("-b", "--bestof", help="Create n crosswords and keep the best", action="store", dest="bestof", default=3, type="int")
    parser.add_option_group(crossword_group)
    
    output_group = OptionGroup(parser, "Output Options")
    output_group.add_option("--print-clues", help="Print crossword clues to stdout", action="store_true", dest="print_clues", default=False)
    output_group.add_option("--print-crossword", help="Print crossword to stdout", action="store_true", dest="print_crossword", default=False)
    output_group.add_option("--create-image", help="Create a crossword image", action="store_true", dest="create_image", default=False)
    output_group.add_option("-o", "--output", help="Specify filename (only for --create-image). If no filename is give, the name will be generated from the input file. If you specify multiple input files and an output file, numbers will be appended to the given output-filename", action="store", dest="output", default=None)
    parser.add_option_group(output_group)
    
    image_group = OptionGroup(parser, "Image Options", "These options can be used to specify the image to be generated")
    image_group.add_option("-p", "--pixels", help="Number of pixels per block for the corssword image", action="store", dest="ppb", default=32, type="int")
    parser.add_option_group(image_group)
    (options, args) = parser.parse_args()
    
    if options.benchmark:
        if options.bsettings:
            w, n, b = options.bsettings.split(",")
        run_benchmark_test(words=int(w.strip()), num=int(n.strip()), bestof=int(b.strip()))
        sys.exit(0)
    
    if args == []:
        parser.print_help()
        print("You need to specify an input file")
        sys.exit(0)
    if not options.create_image and not options.print_crossword:
        parser.print_help()
        print("You need to specify the desired output format")
        sys.exit(0)
    #~ if not options.output and options.create_image:
        #~ parser.print_help()
        #~ print("You need to specify the desired output file")
        #~ sys.exit(0)
    
    if options.columns.isdigit():
        options.columns = int(options.columns)
    if options.rows.isdigit():
        options.rows = int(options.rows)
    
    #~ input = []
    #~ for filename in args:
        #~ input += glob.glob(filename)
    #~ print options.input

    counter = 0
    for inputfile in args:
        if len(args) == 1:
            if options.output:
                output = options.output
            else:
                output = "%s.png" % os.path.splitext(inputfile)[0]
                c = 1
                while os.path.exists(output):
                    output = "%s_%i.png" % (os.path.splitext(inputfile)[0], c)
                    c += 1
        else:
            if options.output:
                filename = options.output
            else:
                filename = inputfile
            output = "%s.png" % (os.path.splitext(filename)[0])
            c = 1
            while os.path.exists(output):
                output = "%s_%i.png" % (os.path.splitext(filename)[0], c)
                c += 1

        parser = SimpleParser(inputfile)
        if options.solution:
            solution = options.solution
        elif parser.has_option("solution"):
            solution = parser.get_option("solution")
        else:
            solution = None
        
        wordlist = parser.get_questions()
        cwd = CrossWord(options.columns, options.rows, " ", 5000, wordlist)
        score = cwd.compute_crossword(best_of=options.bestof, force_solved=False)   
    
        tmplist = [w.word.lower() for w in cwd.placed_words]
        missing = [w.word for w in cwd.wordlist if w.word.lower() not in tmplist]
        if missing != []:
            print("Could not place some words. Probably your grid is too small. Sometimes setting \"--bestof\" to a higer value also help.")
            print("Words that could not be placed: '%s'" % missing)
    
        if options.stats:
            stats(cwd, False)
    
        formatter = CrossWordFormatter(cwd, ppb=options.ppb, solution=solution)
            
        if options.create_image:
            formatter.get_crossword_image_grid(output=output)
            if options.solved:
                formatter.get_crossword_image_grid(output=output.replace(".png", "_solved.png"), solved=True)
        if options.print_crossword:
            print formatter.get_crossword_ascii_grid(False, True)
            print "Sorry, the print-crossword-formatter is still buggy!\n"
        if options.print_clues:
            print formatter.get_crossword_ascii_cues()
            
        counter += 1
