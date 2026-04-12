# Generated from src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

if "." in __name__:
    from .PinescriptParserBase import PinescriptParserBase
else:
    from PinescriptParserBase import PinescriptParserBase

def serializedATN():
    return [
        4,1,64,861,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,2,18,7,18,2,19,7,19,2,20,
        7,20,2,21,7,21,2,22,7,22,2,23,7,23,2,24,7,24,2,25,7,25,2,26,7,26,
        2,27,7,27,2,28,7,28,2,29,7,29,2,30,7,30,2,31,7,31,2,32,7,32,2,33,
        7,33,2,34,7,34,2,35,7,35,2,36,7,36,2,37,7,37,2,38,7,38,2,39,7,39,
        2,40,7,40,2,41,7,41,2,42,7,42,2,43,7,43,2,44,7,44,2,45,7,45,2,46,
        7,46,2,47,7,47,2,48,7,48,2,49,7,49,2,50,7,50,2,51,7,51,2,52,7,52,
        2,53,7,53,2,54,7,54,2,55,7,55,2,56,7,56,2,57,7,57,2,58,7,58,2,59,
        7,59,2,60,7,60,2,61,7,61,2,62,7,62,2,63,7,63,2,64,7,64,2,65,7,65,
        2,66,7,66,2,67,7,67,2,68,7,68,2,69,7,69,2,70,7,70,2,71,7,71,2,72,
        7,72,2,73,7,73,2,74,7,74,2,75,7,75,2,76,7,76,2,77,7,77,2,78,7,78,
        2,79,7,79,2,80,7,80,2,81,7,81,2,82,7,82,2,83,7,83,2,84,7,84,2,85,
        7,85,2,86,7,86,2,87,7,87,2,88,7,88,2,89,7,89,2,90,7,90,2,91,7,91,
        2,92,7,92,2,93,7,93,2,94,7,94,2,95,7,95,2,96,7,96,2,97,7,97,2,98,
        7,98,2,99,7,99,2,100,7,100,2,101,7,101,2,102,7,102,2,103,7,103,2,
        104,7,104,2,105,7,105,2,106,7,106,2,107,7,107,2,108,7,108,2,109,
        7,109,2,110,7,110,1,0,1,0,1,1,3,1,226,8,1,1,1,1,1,1,2,1,2,3,2,232,
        8,2,1,2,1,2,1,3,3,3,237,8,3,1,3,1,3,1,4,4,4,242,8,4,11,4,12,4,243,
        1,5,1,5,3,5,248,8,5,1,6,1,6,1,6,1,6,1,6,1,6,3,6,256,8,6,1,7,1,7,
        1,7,5,7,261,8,7,10,7,12,7,264,9,7,1,7,3,7,267,8,7,1,7,1,7,1,8,1,
        8,1,8,1,8,1,8,3,8,276,8,8,1,9,1,9,1,9,3,9,281,8,9,1,10,1,10,3,10,
        285,8,10,1,11,1,11,1,11,1,11,1,12,1,12,1,12,1,12,1,13,1,13,1,13,
        1,13,1,14,1,14,1,14,1,14,1,15,3,15,304,8,15,1,15,1,15,1,15,3,15,
        309,8,15,1,15,1,15,1,15,1,15,1,16,1,16,1,16,5,16,318,8,16,10,16,
        12,16,321,9,16,1,16,3,16,324,8,16,1,17,3,17,327,8,17,1,17,1,17,1,
        17,3,17,332,8,17,1,18,3,18,335,8,18,1,18,1,18,1,18,1,18,3,18,341,
        8,18,1,18,1,18,1,18,1,18,1,19,1,19,1,19,5,19,350,8,19,10,19,12,19,
        353,9,19,1,19,3,19,356,8,19,1,20,1,20,1,20,1,20,3,20,362,8,20,1,
        21,3,21,365,8,21,1,21,1,21,1,21,1,21,1,21,1,21,1,21,1,22,4,22,375,
        8,22,11,22,12,22,376,1,23,3,23,380,8,23,1,23,1,23,1,23,1,23,3,23,
        386,8,23,1,23,1,23,1,24,3,24,391,8,24,1,24,1,24,1,24,1,24,1,24,1,
        24,1,24,1,25,4,25,401,8,25,11,25,12,25,402,1,26,1,26,1,26,3,26,408,
        8,26,1,26,1,26,1,27,1,27,1,27,1,27,3,27,416,8,27,1,28,1,28,1,29,
        1,29,1,30,1,30,3,30,424,8,30,1,31,1,31,1,31,1,31,1,31,1,32,1,32,
        1,32,1,32,3,32,435,8,32,1,33,1,33,3,33,439,8,33,1,34,1,34,1,34,1,
        34,1,34,1,34,1,35,1,35,1,35,1,35,1,35,3,35,452,8,35,1,36,1,36,1,
        36,1,37,1,37,3,37,459,8,37,1,38,1,38,1,38,1,38,1,38,1,38,1,38,1,
        38,3,38,469,8,38,1,38,1,38,1,39,1,39,1,39,1,39,1,39,1,39,1,40,1,
        40,3,40,481,8,40,1,41,1,41,1,41,1,41,1,42,1,42,3,42,489,8,42,1,42,
        1,42,1,42,1,42,1,42,1,43,4,43,497,8,43,11,43,12,43,498,1,43,3,43,
        502,8,43,1,44,1,44,1,44,1,44,1,45,1,45,1,45,1,46,1,46,3,46,513,8,
        46,1,47,1,47,1,47,1,47,1,47,1,48,1,48,1,49,1,49,1,49,3,49,525,8,
        49,1,50,1,50,3,50,529,8,50,1,51,1,51,1,51,1,51,1,52,1,52,1,52,1,
        52,1,53,1,53,1,53,1,53,1,54,1,54,1,54,1,54,1,55,1,55,1,56,1,56,1,
        57,1,57,1,57,1,57,1,57,1,57,3,57,557,8,57,1,58,1,58,1,58,5,58,562,
        8,58,10,58,12,58,565,9,58,1,59,1,59,1,59,5,59,570,8,59,10,59,12,
        59,573,9,59,1,60,1,60,5,60,577,8,60,10,60,12,60,580,9,60,1,61,1,
        61,3,61,584,8,61,1,62,1,62,1,62,1,63,1,63,1,63,1,64,1,64,5,64,594,
        8,64,10,64,12,64,597,9,64,1,65,1,65,1,65,1,65,3,65,603,8,65,1,66,
        1,66,1,66,1,67,1,67,1,67,1,68,1,68,1,68,1,69,1,69,1,69,1,70,1,70,
        1,70,1,70,1,70,1,70,1,70,5,70,624,8,70,10,70,12,70,627,9,70,1,71,
        1,71,1,72,1,72,1,72,1,72,1,72,1,72,1,72,5,72,638,8,72,10,72,12,72,
        641,9,72,1,73,1,73,1,74,1,74,1,74,1,74,3,74,649,8,74,1,75,1,75,1,
        76,1,76,1,76,1,76,1,76,1,76,1,76,1,76,3,76,661,8,76,1,76,1,76,3,
        76,665,8,76,1,76,1,76,1,76,1,76,1,76,1,76,5,76,673,8,76,10,76,12,
        76,676,9,76,1,77,1,77,1,77,5,77,681,8,77,10,77,12,77,684,9,77,1,
        77,3,77,687,8,77,1,78,1,78,1,78,3,78,692,8,78,1,78,1,78,1,79,1,79,
        1,79,5,79,699,8,79,10,79,12,79,702,9,79,1,79,3,79,705,8,79,1,80,
        1,80,1,80,1,80,3,80,711,8,80,1,81,1,81,1,81,1,81,3,81,717,8,81,1,
        82,1,82,1,83,1,83,1,84,1,84,1,85,1,85,1,86,1,86,1,86,1,86,1,87,1,
        87,1,87,1,87,5,87,735,8,87,10,87,12,87,738,9,87,1,87,3,87,741,8,
        87,3,87,743,8,87,1,87,1,87,1,88,1,88,1,88,1,88,1,88,1,88,1,88,1,
        88,3,88,755,8,88,1,89,1,89,1,90,1,90,1,91,3,91,762,8,91,1,91,3,91,
        765,8,91,1,91,1,91,1,92,1,92,1,92,1,92,5,92,773,8,92,10,92,12,92,
        776,9,92,1,92,3,92,779,8,92,1,92,1,92,1,93,1,93,1,94,1,94,1,94,1,
        94,3,94,789,8,94,1,95,1,95,1,95,1,95,1,96,1,96,1,96,1,96,1,96,1,
        97,1,97,1,98,1,98,1,98,1,98,1,99,1,99,1,100,3,100,809,8,100,1,100,
        1,100,3,100,813,8,100,1,100,3,100,816,8,100,1,101,1,101,1,102,1,
        102,1,102,5,102,823,8,102,10,102,12,102,826,9,102,1,103,1,103,3,
        103,830,8,103,1,103,1,103,1,104,1,104,1,104,1,105,1,105,1,105,5,
        105,840,8,105,10,105,12,105,843,9,105,1,105,3,105,846,8,105,1,106,
        1,106,1,107,1,107,1,108,1,108,1,109,4,109,855,8,109,11,109,12,109,
        856,1,110,1,110,1,110,0,3,140,144,152,111,0,2,4,6,8,10,12,14,16,
        18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48,50,52,54,56,58,60,
        62,64,66,68,70,72,74,76,78,80,82,84,86,88,90,92,94,96,98,100,102,
        104,106,108,110,112,114,116,118,120,122,124,126,128,130,132,134,
        136,138,140,142,144,146,148,150,152,154,156,158,160,162,164,166,
        168,170,172,174,176,178,180,182,184,186,188,190,192,194,196,198,
        200,202,204,206,208,210,212,214,216,218,220,0,8,1,0,46,47,1,0,48,
        50,2,0,19,19,46,47,2,0,12,12,26,26,1,0,27,28,1,0,51,55,3,0,7,7,17,
        17,21,22,6,0,7,7,10,10,17,18,21,22,25,25,57,57,850,0,222,1,0,0,0,
        2,225,1,0,0,0,4,229,1,0,0,0,6,236,1,0,0,0,8,241,1,0,0,0,10,247,1,
        0,0,0,12,255,1,0,0,0,14,257,1,0,0,0,16,275,1,0,0,0,18,280,1,0,0,
        0,20,284,1,0,0,0,22,286,1,0,0,0,24,290,1,0,0,0,26,294,1,0,0,0,28,
        298,1,0,0,0,30,303,1,0,0,0,32,314,1,0,0,0,34,326,1,0,0,0,36,334,
        1,0,0,0,38,346,1,0,0,0,40,361,1,0,0,0,42,364,1,0,0,0,44,374,1,0,
        0,0,46,379,1,0,0,0,48,390,1,0,0,0,50,400,1,0,0,0,52,404,1,0,0,0,
        54,415,1,0,0,0,56,417,1,0,0,0,58,419,1,0,0,0,60,423,1,0,0,0,62,425,
        1,0,0,0,64,430,1,0,0,0,66,438,1,0,0,0,68,440,1,0,0,0,70,446,1,0,
        0,0,72,453,1,0,0,0,74,458,1,0,0,0,76,460,1,0,0,0,78,472,1,0,0,0,
        80,480,1,0,0,0,82,482,1,0,0,0,84,486,1,0,0,0,86,496,1,0,0,0,88,503,
        1,0,0,0,90,507,1,0,0,0,92,512,1,0,0,0,94,514,1,0,0,0,96,519,1,0,
        0,0,98,524,1,0,0,0,100,528,1,0,0,0,102,530,1,0,0,0,104,534,1,0,0,
        0,106,538,1,0,0,0,108,542,1,0,0,0,110,546,1,0,0,0,112,548,1,0,0,
        0,114,550,1,0,0,0,116,558,1,0,0,0,118,566,1,0,0,0,120,574,1,0,0,
        0,122,583,1,0,0,0,124,585,1,0,0,0,126,588,1,0,0,0,128,591,1,0,0,
        0,130,602,1,0,0,0,132,604,1,0,0,0,134,607,1,0,0,0,136,610,1,0,0,
        0,138,613,1,0,0,0,140,616,1,0,0,0,142,628,1,0,0,0,144,630,1,0,0,
        0,146,642,1,0,0,0,148,648,1,0,0,0,150,650,1,0,0,0,152,652,1,0,0,
        0,154,677,1,0,0,0,156,691,1,0,0,0,158,695,1,0,0,0,160,710,1,0,0,
        0,162,716,1,0,0,0,164,718,1,0,0,0,166,720,1,0,0,0,168,722,1,0,0,
        0,170,724,1,0,0,0,172,726,1,0,0,0,174,730,1,0,0,0,176,746,1,0,0,
        0,178,756,1,0,0,0,180,758,1,0,0,0,182,761,1,0,0,0,184,768,1,0,0,
        0,186,782,1,0,0,0,188,788,1,0,0,0,190,790,1,0,0,0,192,794,1,0,0,
        0,194,799,1,0,0,0,196,801,1,0,0,0,198,805,1,0,0,0,200,808,1,0,0,
        0,202,817,1,0,0,0,204,819,1,0,0,0,206,827,1,0,0,0,208,833,1,0,0,
        0,210,836,1,0,0,0,212,847,1,0,0,0,214,849,1,0,0,0,216,851,1,0,0,
        0,218,854,1,0,0,0,220,858,1,0,0,0,222,223,3,2,1,0,223,1,1,0,0,0,
        224,226,3,8,4,0,225,224,1,0,0,0,225,226,1,0,0,0,226,227,1,0,0,0,
        227,228,5,0,0,1,228,3,1,0,0,0,229,231,3,110,55,0,230,232,5,61,0,
        0,231,230,1,0,0,0,231,232,1,0,0,0,232,233,1,0,0,0,233,234,5,0,0,
        1,234,5,1,0,0,0,235,237,3,218,109,0,236,235,1,0,0,0,236,237,1,0,
        0,0,237,238,1,0,0,0,238,239,5,0,0,1,239,7,1,0,0,0,240,242,3,10,5,
        0,241,240,1,0,0,0,242,243,1,0,0,0,243,241,1,0,0,0,243,244,1,0,0,
        0,244,9,1,0,0,0,245,248,3,12,6,0,246,248,3,14,7,0,247,245,1,0,0,
        0,247,246,1,0,0,0,248,11,1,0,0,0,249,256,3,18,9,0,250,256,3,42,21,
        0,251,256,3,48,24,0,252,256,3,56,28,0,253,256,3,36,18,0,254,256,
        3,30,15,0,255,249,1,0,0,0,255,250,1,0,0,0,255,251,1,0,0,0,255,252,
        1,0,0,0,255,253,1,0,0,0,255,254,1,0,0,0,256,13,1,0,0,0,257,262,3,
        16,8,0,258,259,5,43,0,0,259,261,3,16,8,0,260,258,1,0,0,0,261,264,
        1,0,0,0,262,260,1,0,0,0,262,263,1,0,0,0,263,266,1,0,0,0,264,262,
        1,0,0,0,265,267,5,43,0,0,266,265,1,0,0,0,266,267,1,0,0,0,267,268,
        1,0,0,0,268,269,5,61,0,0,269,15,1,0,0,0,270,276,3,98,49,0,271,276,
        3,112,56,0,272,276,3,176,88,0,273,276,3,178,89,0,274,276,3,180,90,
        0,275,270,1,0,0,0,275,271,1,0,0,0,275,272,1,0,0,0,275,273,1,0,0,
        0,275,274,1,0,0,0,276,17,1,0,0,0,277,281,3,20,10,0,278,281,3,26,
        13,0,279,281,3,28,14,0,280,277,1,0,0,0,280,278,1,0,0,0,280,279,1,
        0,0,0,281,19,1,0,0,0,282,285,3,22,11,0,283,285,3,24,12,0,284,282,
        1,0,0,0,284,283,1,0,0,0,285,21,1,0,0,0,286,287,3,182,91,0,287,288,
        5,36,0,0,288,289,3,58,29,0,289,23,1,0,0,0,290,291,3,184,92,0,291,
        292,5,36,0,0,292,293,3,58,29,0,293,25,1,0,0,0,294,295,3,188,94,0,
        295,296,5,56,0,0,296,297,3,58,29,0,297,27,1,0,0,0,298,299,3,188,
        94,0,299,300,3,198,99,0,300,301,3,58,29,0,301,29,1,0,0,0,302,304,
        5,11,0,0,303,302,1,0,0,0,303,304,1,0,0,0,304,305,1,0,0,0,305,306,
        3,212,106,0,306,308,5,30,0,0,307,309,3,32,16,0,308,307,1,0,0,0,308,
        309,1,0,0,0,309,310,1,0,0,0,310,311,5,31,0,0,311,312,5,41,0,0,312,
        313,3,92,46,0,313,31,1,0,0,0,314,319,3,34,17,0,315,316,5,43,0,0,
        316,318,3,34,17,0,317,315,1,0,0,0,318,321,1,0,0,0,319,317,1,0,0,
        0,319,320,1,0,0,0,320,323,1,0,0,0,321,319,1,0,0,0,322,324,5,43,0,
        0,323,322,1,0,0,0,323,324,1,0,0,0,324,33,1,0,0,0,325,327,3,200,100,
        0,326,325,1,0,0,0,326,327,1,0,0,0,327,328,1,0,0,0,328,331,3,216,
        108,0,329,330,5,36,0,0,330,332,3,110,55,0,331,329,1,0,0,0,331,332,
        1,0,0,0,332,35,1,0,0,0,333,335,5,11,0,0,334,333,1,0,0,0,334,335,
        1,0,0,0,335,336,1,0,0,0,336,337,5,18,0,0,337,338,3,212,106,0,338,
        340,5,30,0,0,339,341,3,38,19,0,340,339,1,0,0,0,340,341,1,0,0,0,341,
        342,1,0,0,0,342,343,5,31,0,0,343,344,5,41,0,0,344,345,3,92,46,0,
        345,37,1,0,0,0,346,351,3,40,20,0,347,348,5,43,0,0,348,350,3,40,20,
        0,349,347,1,0,0,0,350,353,1,0,0,0,351,349,1,0,0,0,351,352,1,0,0,
        0,352,355,1,0,0,0,353,351,1,0,0,0,354,356,5,43,0,0,355,354,1,0,0,
        0,355,356,1,0,0,0,356,39,1,0,0,0,357,358,3,200,100,0,358,359,3,216,
        108,0,359,362,1,0,0,0,360,362,3,34,17,0,361,357,1,0,0,0,361,360,
        1,0,0,0,362,41,1,0,0,0,363,365,5,11,0,0,364,363,1,0,0,0,364,365,
        1,0,0,0,365,366,1,0,0,0,366,367,5,25,0,0,367,368,3,212,106,0,368,
        369,5,61,0,0,369,370,5,1,0,0,370,371,3,44,22,0,371,372,5,2,0,0,372,
        43,1,0,0,0,373,375,3,46,23,0,374,373,1,0,0,0,375,376,1,0,0,0,376,
        374,1,0,0,0,376,377,1,0,0,0,377,45,1,0,0,0,378,380,5,28,0,0,379,
        378,1,0,0,0,379,380,1,0,0,0,380,381,1,0,0,0,381,382,3,200,100,0,
        382,385,3,216,108,0,383,384,5,36,0,0,384,386,3,110,55,0,385,383,
        1,0,0,0,385,386,1,0,0,0,386,387,1,0,0,0,387,388,5,61,0,0,388,47,
        1,0,0,0,389,391,5,11,0,0,390,389,1,0,0,0,390,391,1,0,0,0,391,392,
        1,0,0,0,392,393,5,10,0,0,393,394,3,212,106,0,394,395,5,61,0,0,395,
        396,5,1,0,0,396,397,3,50,25,0,397,398,5,2,0,0,398,49,1,0,0,0,399,
        401,3,52,26,0,400,399,1,0,0,0,401,402,1,0,0,0,402,400,1,0,0,0,402,
        403,1,0,0,0,403,51,1,0,0,0,404,407,3,216,108,0,405,406,5,36,0,0,
        406,408,3,110,55,0,407,405,1,0,0,0,407,408,1,0,0,0,408,409,1,0,0,
        0,409,410,5,61,0,0,410,53,1,0,0,0,411,416,3,60,30,0,412,416,3,74,
        37,0,413,416,3,82,41,0,414,416,3,84,42,0,415,411,1,0,0,0,415,412,
        1,0,0,0,415,413,1,0,0,0,415,414,1,0,0,0,416,55,1,0,0,0,417,418,3,
        54,27,0,418,57,1,0,0,0,419,420,3,54,27,0,420,59,1,0,0,0,421,424,
        3,62,31,0,422,424,3,64,32,0,423,421,1,0,0,0,423,422,1,0,0,0,424,
        61,1,0,0,0,425,426,5,14,0,0,426,427,3,110,55,0,427,428,3,92,46,0,
        428,429,3,66,33,0,429,63,1,0,0,0,430,431,5,14,0,0,431,432,3,110,
        55,0,432,434,3,92,46,0,433,435,3,72,36,0,434,433,1,0,0,0,434,435,
        1,0,0,0,435,65,1,0,0,0,436,439,3,68,34,0,437,439,3,70,35,0,438,436,
        1,0,0,0,438,437,1,0,0,0,439,67,1,0,0,0,440,441,5,9,0,0,441,442,5,
        14,0,0,442,443,3,110,55,0,443,444,3,92,46,0,444,445,3,66,33,0,445,
        69,1,0,0,0,446,447,5,9,0,0,447,448,5,14,0,0,448,449,3,110,55,0,449,
        451,3,92,46,0,450,452,3,72,36,0,451,450,1,0,0,0,451,452,1,0,0,0,
        452,71,1,0,0,0,453,454,5,9,0,0,454,455,3,92,46,0,455,73,1,0,0,0,
        456,459,3,76,38,0,457,459,3,78,39,0,458,456,1,0,0,0,458,457,1,0,
        0,0,459,75,1,0,0,0,460,461,5,13,0,0,461,462,3,80,40,0,462,463,5,
        36,0,0,463,464,3,110,55,0,464,465,5,24,0,0,465,468,3,110,55,0,466,
        467,5,6,0,0,467,469,3,110,55,0,468,466,1,0,0,0,468,469,1,0,0,0,469,
        470,1,0,0,0,470,471,3,92,46,0,471,77,1,0,0,0,472,473,5,13,0,0,473,
        474,3,80,40,0,474,475,5,16,0,0,475,476,3,110,55,0,476,477,3,92,46,
        0,477,79,1,0,0,0,478,481,3,216,108,0,479,481,3,184,92,0,480,478,
        1,0,0,0,480,479,1,0,0,0,481,81,1,0,0,0,482,483,5,29,0,0,483,484,
        3,110,55,0,484,485,3,92,46,0,485,83,1,0,0,0,486,488,5,23,0,0,487,
        489,3,110,55,0,488,487,1,0,0,0,488,489,1,0,0,0,489,490,1,0,0,0,490,
        491,5,61,0,0,491,492,5,1,0,0,492,493,3,86,43,0,493,494,5,2,0,0,494,
        85,1,0,0,0,495,497,3,88,44,0,496,495,1,0,0,0,497,498,1,0,0,0,498,
        496,1,0,0,0,498,499,1,0,0,0,499,501,1,0,0,0,500,502,3,90,45,0,501,
        500,1,0,0,0,501,502,1,0,0,0,502,87,1,0,0,0,503,504,3,110,55,0,504,
        505,5,41,0,0,505,506,3,92,46,0,506,89,1,0,0,0,507,508,5,41,0,0,508,
        509,3,92,46,0,509,91,1,0,0,0,510,513,3,94,47,0,511,513,3,96,48,0,
        512,510,1,0,0,0,512,511,1,0,0,0,513,93,1,0,0,0,514,515,5,61,0,0,
        515,516,5,1,0,0,516,517,3,8,4,0,517,518,5,2,0,0,518,95,1,0,0,0,519,
        520,3,10,5,0,520,97,1,0,0,0,521,525,3,100,50,0,522,525,3,106,53,
        0,523,525,3,108,54,0,524,521,1,0,0,0,524,522,1,0,0,0,524,523,1,0,
        0,0,525,99,1,0,0,0,526,529,3,102,51,0,527,529,3,104,52,0,528,526,
        1,0,0,0,528,527,1,0,0,0,529,101,1,0,0,0,530,531,3,182,91,0,531,532,
        5,36,0,0,532,533,3,110,55,0,533,103,1,0,0,0,534,535,3,184,92,0,535,
        536,5,36,0,0,536,537,3,110,55,0,537,105,1,0,0,0,538,539,3,188,94,
        0,539,540,5,56,0,0,540,541,3,110,55,0,541,107,1,0,0,0,542,543,3,
        188,94,0,543,544,3,198,99,0,544,545,3,110,55,0,545,109,1,0,0,0,546,
        547,3,114,57,0,547,111,1,0,0,0,548,549,3,110,55,0,549,113,1,0,0,
        0,550,556,3,116,58,0,551,552,5,45,0,0,552,553,3,110,55,0,553,554,
        5,44,0,0,554,555,3,110,55,0,555,557,1,0,0,0,556,551,1,0,0,0,556,
        557,1,0,0,0,557,115,1,0,0,0,558,563,3,118,59,0,559,560,5,20,0,0,
        560,562,3,118,59,0,561,559,1,0,0,0,562,565,1,0,0,0,563,561,1,0,0,
        0,563,564,1,0,0,0,564,117,1,0,0,0,565,563,1,0,0,0,566,571,3,120,
        60,0,567,568,5,3,0,0,568,570,3,120,60,0,569,567,1,0,0,0,570,573,
        1,0,0,0,571,569,1,0,0,0,571,572,1,0,0,0,572,119,1,0,0,0,573,571,
        1,0,0,0,574,578,3,128,64,0,575,577,3,122,61,0,576,575,1,0,0,0,577,
        580,1,0,0,0,578,576,1,0,0,0,578,579,1,0,0,0,579,121,1,0,0,0,580,
        578,1,0,0,0,581,584,3,124,62,0,582,584,3,126,63,0,583,581,1,0,0,
        0,583,582,1,0,0,0,584,123,1,0,0,0,585,586,5,37,0,0,586,587,3,128,
        64,0,587,125,1,0,0,0,588,589,5,38,0,0,589,590,3,128,64,0,590,127,
        1,0,0,0,591,595,3,140,70,0,592,594,3,130,65,0,593,592,1,0,0,0,594,
        597,1,0,0,0,595,593,1,0,0,0,595,596,1,0,0,0,596,129,1,0,0,0,597,
        595,1,0,0,0,598,603,3,132,66,0,599,603,3,134,67,0,600,603,3,136,
        68,0,601,603,3,138,69,0,602,598,1,0,0,0,602,599,1,0,0,0,602,600,
        1,0,0,0,602,601,1,0,0,0,603,131,1,0,0,0,604,605,5,39,0,0,605,606,
        3,140,70,0,606,133,1,0,0,0,607,608,5,34,0,0,608,609,3,140,70,0,609,
        135,1,0,0,0,610,611,5,40,0,0,611,612,3,140,70,0,612,137,1,0,0,0,
        613,614,5,35,0,0,614,615,3,140,70,0,615,139,1,0,0,0,616,617,6,70,
        -1,0,617,618,3,144,72,0,618,625,1,0,0,0,619,620,10,2,0,0,620,621,
        3,142,71,0,621,622,3,144,72,0,622,624,1,0,0,0,623,619,1,0,0,0,624,
        627,1,0,0,0,625,623,1,0,0,0,625,626,1,0,0,0,626,141,1,0,0,0,627,
        625,1,0,0,0,628,629,7,0,0,0,629,143,1,0,0,0,630,631,6,72,-1,0,631,
        632,3,148,74,0,632,639,1,0,0,0,633,634,10,2,0,0,634,635,3,146,73,
        0,635,636,3,148,74,0,636,638,1,0,0,0,637,633,1,0,0,0,638,641,1,0,
        0,0,639,637,1,0,0,0,639,640,1,0,0,0,640,145,1,0,0,0,641,639,1,0,
        0,0,642,643,7,1,0,0,643,147,1,0,0,0,644,645,3,150,75,0,645,646,3,
        148,74,0,646,649,1,0,0,0,647,649,3,152,76,0,648,644,1,0,0,0,648,
        647,1,0,0,0,649,149,1,0,0,0,650,651,7,2,0,0,651,151,1,0,0,0,652,
        653,6,76,-1,0,653,654,3,160,80,0,654,674,1,0,0,0,655,656,10,4,0,
        0,656,657,5,42,0,0,657,673,3,214,107,0,658,660,10,3,0,0,659,661,
        3,206,103,0,660,659,1,0,0,0,660,661,1,0,0,0,661,662,1,0,0,0,662,
        664,5,30,0,0,663,665,3,154,77,0,664,663,1,0,0,0,664,665,1,0,0,0,
        665,666,1,0,0,0,666,673,5,31,0,0,667,668,10,2,0,0,668,669,5,32,0,
        0,669,670,3,158,79,0,670,671,5,33,0,0,671,673,1,0,0,0,672,655,1,
        0,0,0,672,658,1,0,0,0,672,667,1,0,0,0,673,676,1,0,0,0,674,672,1,
        0,0,0,674,675,1,0,0,0,675,153,1,0,0,0,676,674,1,0,0,0,677,682,3,
        156,78,0,678,679,5,43,0,0,679,681,3,156,78,0,680,678,1,0,0,0,681,
        684,1,0,0,0,682,680,1,0,0,0,682,683,1,0,0,0,683,686,1,0,0,0,684,
        682,1,0,0,0,685,687,5,43,0,0,686,685,1,0,0,0,686,687,1,0,0,0,687,
        155,1,0,0,0,688,689,3,216,108,0,689,690,5,36,0,0,690,692,1,0,0,0,
        691,688,1,0,0,0,691,692,1,0,0,0,692,693,1,0,0,0,693,694,3,110,55,
        0,694,157,1,0,0,0,695,700,3,110,55,0,696,697,5,43,0,0,697,699,3,
        110,55,0,698,696,1,0,0,0,699,702,1,0,0,0,700,698,1,0,0,0,700,701,
        1,0,0,0,701,704,1,0,0,0,702,700,1,0,0,0,703,705,5,43,0,0,704,703,
        1,0,0,0,704,705,1,0,0,0,705,159,1,0,0,0,706,711,3,214,107,0,707,
        711,3,162,81,0,708,711,3,172,86,0,709,711,3,174,87,0,710,706,1,0,
        0,0,710,707,1,0,0,0,710,708,1,0,0,0,710,709,1,0,0,0,711,161,1,0,
        0,0,712,717,3,164,82,0,713,717,3,166,83,0,714,717,3,168,84,0,715,
        717,3,170,85,0,716,712,1,0,0,0,716,713,1,0,0,0,716,714,1,0,0,0,716,
        715,1,0,0,0,717,163,1,0,0,0,718,719,5,58,0,0,719,165,1,0,0,0,720,
        721,5,59,0,0,721,167,1,0,0,0,722,723,7,3,0,0,723,169,1,0,0,0,724,
        725,5,60,0,0,725,171,1,0,0,0,726,727,5,30,0,0,727,728,3,110,55,0,
        728,729,5,31,0,0,729,173,1,0,0,0,730,742,5,32,0,0,731,736,3,110,
        55,0,732,733,5,43,0,0,733,735,3,110,55,0,734,732,1,0,0,0,735,738,
        1,0,0,0,736,734,1,0,0,0,736,737,1,0,0,0,737,740,1,0,0,0,738,736,
        1,0,0,0,739,741,5,43,0,0,740,739,1,0,0,0,740,741,1,0,0,0,741,743,
        1,0,0,0,742,731,1,0,0,0,742,743,1,0,0,0,743,744,1,0,0,0,744,745,
        5,33,0,0,745,175,1,0,0,0,746,747,5,15,0,0,747,748,3,212,106,0,748,
        749,5,49,0,0,749,750,3,212,106,0,750,751,5,49,0,0,751,754,3,164,
        82,0,752,753,5,4,0,0,753,755,3,212,106,0,754,752,1,0,0,0,754,755,
        1,0,0,0,755,177,1,0,0,0,756,757,5,5,0,0,757,179,1,0,0,0,758,759,
        5,8,0,0,759,181,1,0,0,0,760,762,3,186,93,0,761,760,1,0,0,0,761,762,
        1,0,0,0,762,764,1,0,0,0,763,765,3,200,100,0,764,763,1,0,0,0,764,
        765,1,0,0,0,765,766,1,0,0,0,766,767,3,216,108,0,767,183,1,0,0,0,
        768,769,5,32,0,0,769,774,3,216,108,0,770,771,5,43,0,0,771,773,3,
        216,108,0,772,770,1,0,0,0,773,776,1,0,0,0,774,772,1,0,0,0,774,775,
        1,0,0,0,775,778,1,0,0,0,776,774,1,0,0,0,777,779,5,43,0,0,778,777,
        1,0,0,0,778,779,1,0,0,0,779,780,1,0,0,0,780,781,5,33,0,0,781,185,
        1,0,0,0,782,783,7,4,0,0,783,187,1,0,0,0,784,789,3,190,95,0,785,789,
        3,192,96,0,786,789,3,194,97,0,787,789,3,196,98,0,788,784,1,0,0,0,
        788,785,1,0,0,0,788,786,1,0,0,0,788,787,1,0,0,0,789,189,1,0,0,0,
        790,791,3,152,76,0,791,792,5,42,0,0,792,793,3,216,108,0,793,191,
        1,0,0,0,794,795,3,152,76,0,795,796,5,32,0,0,796,797,3,158,79,0,797,
        798,5,33,0,0,798,193,1,0,0,0,799,800,3,216,108,0,800,195,1,0,0,0,
        801,802,5,30,0,0,802,803,3,188,94,0,803,804,5,31,0,0,804,197,1,0,
        0,0,805,806,7,5,0,0,806,199,1,0,0,0,807,809,3,202,101,0,808,807,
        1,0,0,0,808,809,1,0,0,0,809,810,1,0,0,0,810,812,3,204,102,0,811,
        813,3,206,103,0,812,811,1,0,0,0,812,813,1,0,0,0,813,815,1,0,0,0,
        814,816,3,208,104,0,815,814,1,0,0,0,815,816,1,0,0,0,816,201,1,0,
        0,0,817,818,7,6,0,0,818,203,1,0,0,0,819,824,3,214,107,0,820,821,
        5,42,0,0,821,823,3,214,107,0,822,820,1,0,0,0,823,826,1,0,0,0,824,
        822,1,0,0,0,824,825,1,0,0,0,825,205,1,0,0,0,826,824,1,0,0,0,827,
        829,5,34,0,0,828,830,3,210,105,0,829,828,1,0,0,0,829,830,1,0,0,0,
        830,831,1,0,0,0,831,832,5,35,0,0,832,207,1,0,0,0,833,834,5,32,0,
        0,834,835,5,33,0,0,835,209,1,0,0,0,836,841,3,200,100,0,837,838,5,
        43,0,0,838,840,3,200,100,0,839,837,1,0,0,0,840,843,1,0,0,0,841,839,
        1,0,0,0,841,842,1,0,0,0,842,845,1,0,0,0,843,841,1,0,0,0,844,846,
        5,43,0,0,845,844,1,0,0,0,845,846,1,0,0,0,846,211,1,0,0,0,847,848,
        7,7,0,0,848,213,1,0,0,0,849,850,3,212,106,0,850,215,1,0,0,0,851,
        852,3,212,106,0,852,217,1,0,0,0,853,855,3,220,110,0,854,853,1,0,
        0,0,855,856,1,0,0,0,856,854,1,0,0,0,856,857,1,0,0,0,857,219,1,0,
        0,0,858,859,5,63,0,0,859,221,1,0,0,0,81,225,231,236,243,247,255,
        262,266,275,280,284,303,308,319,323,326,331,334,340,351,355,361,
        364,376,379,385,390,402,407,415,423,434,438,451,458,468,480,488,
        498,501,512,524,528,556,563,571,578,583,595,602,625,639,648,660,
        664,672,674,682,686,691,700,704,710,716,736,740,742,754,761,764,
        774,778,788,808,812,815,824,829,841,845,856
    ]

class PinescriptParser ( PinescriptParserBase ):

    grammarFileName = "PinescriptParser.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "'and'", "'as'", 
                     "'break'", "'by'", "'const'", "'continue'", "'else'", 
                     "'enum'", "'export'", "'false'", "'for'", "'if'", "'import'", 
                     "'in'", "'input'", "'method'", "'not'", "'or'", "'series'", 
                     "'simple'", "'switch'", "'to'", "'type'", "'true'", 
                     "'var'", "'varip'", "'while'", "'('", "')'", "'['", 
                     "']'", "'<'", "'>'", "'='", "'=='", "'!='", "'<='", 
                     "'>='", "'=>'", "'.'", "','", "':'", "'?'", "'+'", 
                     "'-'", "'*'", "'/'", "'%'", "'+='", "'-='", "'*='", 
                     "'/='", "'%='", "':='" ]

    symbolicNames = [ "<INVALID>", "INDENT", "DEDENT", "AND", "AS", "BREAK", 
                      "BY", "CONST", "CONTINUE", "ELSE", "ENUM", "EXPORT", 
                      "FALSE", "FOR", "IF", "IMPORT", "IN", "INPUT", "METHOD", 
                      "NOT", "OR", "SERIES", "SIMPLE", "SWITCH", "TO", "TYPE", 
                      "TRUE", "VAR", "VARIP", "WHILE", "LPAR", "RPAR", "LSQB", 
                      "RSQB", "LESS", "GREATER", "EQUAL", "EQEQUAL", "NOTEQUAL", 
                      "LESSEQUAL", "GREATEREQUAL", "RARROW", "DOT", "COMMA", 
                      "COLON", "QUESTION", "PLUS", "MINUS", "STAR", "SLASH", 
                      "PERCENT", "PLUSEQUAL", "MINEQUAL", "STAREQUAL", "SLASHEQUAL", 
                      "PERCENTEQUAL", "COLONEQUAL", "NAME", "NUMBER", "STRING", 
                      "COLOR", "NEWLINE", "WS", "COMMENT", "ERROR_TOKEN" ]

    RULE_start = 0
    RULE_start_script = 1
    RULE_start_expression = 2
    RULE_start_comments = 3
    RULE_statements = 4
    RULE_statement = 5
    RULE_compound_statement = 6
    RULE_simple_statements = 7
    RULE_simple_statement = 8
    RULE_compound_assignment = 9
    RULE_compound_variable_initialization = 10
    RULE_compound_name_initialization = 11
    RULE_compound_tuple_initialization = 12
    RULE_compound_reassignment = 13
    RULE_compound_augassignment = 14
    RULE_function_declaration = 15
    RULE_parameter_list = 16
    RULE_parameter_definition = 17
    RULE_method_declaration = 18
    RULE_method_parameter_list = 19
    RULE_method_parameter_definition = 20
    RULE_type_declaration = 21
    RULE_field_definitions = 22
    RULE_field_definition = 23
    RULE_enum_declaration = 24
    RULE_enum_definitions = 25
    RULE_enum_definition = 26
    RULE_structure = 27
    RULE_structure_statement = 28
    RULE_structure_expression = 29
    RULE_if_structure = 30
    RULE_if_structure_elif = 31
    RULE_if_structure_else = 32
    RULE_elif_structure = 33
    RULE_elif_structure_elif = 34
    RULE_elif_structure_else = 35
    RULE_else_block = 36
    RULE_for_structure = 37
    RULE_for_structure_to = 38
    RULE_for_structure_in = 39
    RULE_for_iterator = 40
    RULE_while_structure = 41
    RULE_switch_structure = 42
    RULE_switch_cases = 43
    RULE_switch_pattern_case = 44
    RULE_switch_default_case = 45
    RULE_local_block = 46
    RULE_indented_local_block = 47
    RULE_inline_local_block = 48
    RULE_simple_assignment = 49
    RULE_simple_variable_initialization = 50
    RULE_simple_name_initialization = 51
    RULE_simple_tuple_initialization = 52
    RULE_simple_reassignment = 53
    RULE_simple_augassignment = 54
    RULE_expression = 55
    RULE_expression_statement = 56
    RULE_conditional_expression = 57
    RULE_disjunction_expression = 58
    RULE_conjunction_expression = 59
    RULE_equality_expression = 60
    RULE_equality_trailing_pair = 61
    RULE_equal_trailing_pair = 62
    RULE_not_equal_trailing_pair = 63
    RULE_inequality_expression = 64
    RULE_inequality_trailing_pair = 65
    RULE_less_than_equal_trailing_pair = 66
    RULE_less_than_trailing_pair = 67
    RULE_greater_than_equal_trailing_pair = 68
    RULE_greater_than_trailing_pair = 69
    RULE_additive_expression = 70
    RULE_additive_op = 71
    RULE_multiplicative_expression = 72
    RULE_multiplicative_op = 73
    RULE_unary_expression = 74
    RULE_unary_op = 75
    RULE_primary_expression = 76
    RULE_argument_list = 77
    RULE_argument_definition = 78
    RULE_subscript_slice = 79
    RULE_atomic_expression = 80
    RULE_literal_expression = 81
    RULE_literal_number = 82
    RULE_literal_string = 83
    RULE_literal_bool = 84
    RULE_literal_color = 85
    RULE_grouped_expression = 86
    RULE_tuple_expression = 87
    RULE_import_statement = 88
    RULE_break_statement = 89
    RULE_continue_statement = 90
    RULE_variable_declaration = 91
    RULE_tuple_declaration = 92
    RULE_declaration_mode = 93
    RULE_assignment_target = 94
    RULE_assignment_target_attribute = 95
    RULE_assignment_target_subscript = 96
    RULE_assignment_target_name = 97
    RULE_assignment_target_group = 98
    RULE_augassign_op = 99
    RULE_type_specification = 100
    RULE_type_qualifier = 101
    RULE_attributed_type_name = 102
    RULE_template_spec_suffix = 103
    RULE_array_type_suffix = 104
    RULE_type_argument_list = 105
    RULE_name = 106
    RULE_name_load = 107
    RULE_name_store = 108
    RULE_comments = 109
    RULE_comment = 110

    ruleNames =  [ "start", "start_script", "start_expression", "start_comments", 
                   "statements", "statement", "compound_statement", "simple_statements", 
                   "simple_statement", "compound_assignment", "compound_variable_initialization", 
                   "compound_name_initialization", "compound_tuple_initialization", 
                   "compound_reassignment", "compound_augassignment", "function_declaration", 
                   "parameter_list", "parameter_definition", "method_declaration", 
                   "method_parameter_list", "method_parameter_definition", 
                   "type_declaration", "field_definitions", "field_definition", 
                   "enum_declaration", "enum_definitions", "enum_definition", 
                   "structure", "structure_statement", "structure_expression", 
                   "if_structure", "if_structure_elif", "if_structure_else", 
                   "elif_structure", "elif_structure_elif", "elif_structure_else", 
                   "else_block", "for_structure", "for_structure_to", "for_structure_in", 
                   "for_iterator", "while_structure", "switch_structure", 
                   "switch_cases", "switch_pattern_case", "switch_default_case", 
                   "local_block", "indented_local_block", "inline_local_block", 
                   "simple_assignment", "simple_variable_initialization", 
                   "simple_name_initialization", "simple_tuple_initialization", 
                   "simple_reassignment", "simple_augassignment", "expression", 
                   "expression_statement", "conditional_expression", "disjunction_expression", 
                   "conjunction_expression", "equality_expression", "equality_trailing_pair", 
                   "equal_trailing_pair", "not_equal_trailing_pair", "inequality_expression", 
                   "inequality_trailing_pair", "less_than_equal_trailing_pair", 
                   "less_than_trailing_pair", "greater_than_equal_trailing_pair", 
                   "greater_than_trailing_pair", "additive_expression", 
                   "additive_op", "multiplicative_expression", "multiplicative_op", 
                   "unary_expression", "unary_op", "primary_expression", 
                   "argument_list", "argument_definition", "subscript_slice", 
                   "atomic_expression", "literal_expression", "literal_number", 
                   "literal_string", "literal_bool", "literal_color", "grouped_expression", 
                   "tuple_expression", "import_statement", "break_statement", 
                   "continue_statement", "variable_declaration", "tuple_declaration", 
                   "declaration_mode", "assignment_target", "assignment_target_attribute", 
                   "assignment_target_subscript", "assignment_target_name", 
                   "assignment_target_group", "augassign_op", "type_specification", 
                   "type_qualifier", "attributed_type_name", "template_spec_suffix", 
                   "array_type_suffix", "type_argument_list", "name", "name_load", 
                   "name_store", "comments", "comment" ]

    EOF = Token.EOF
    INDENT=1
    DEDENT=2
    AND=3
    AS=4
    BREAK=5
    BY=6
    CONST=7
    CONTINUE=8
    ELSE=9
    ENUM=10
    EXPORT=11
    FALSE=12
    FOR=13
    IF=14
    IMPORT=15
    IN=16
    INPUT=17
    METHOD=18
    NOT=19
    OR=20
    SERIES=21
    SIMPLE=22
    SWITCH=23
    TO=24
    TYPE=25
    TRUE=26
    VAR=27
    VARIP=28
    WHILE=29
    LPAR=30
    RPAR=31
    LSQB=32
    RSQB=33
    LESS=34
    GREATER=35
    EQUAL=36
    EQEQUAL=37
    NOTEQUAL=38
    LESSEQUAL=39
    GREATEREQUAL=40
    RARROW=41
    DOT=42
    COMMA=43
    COLON=44
    QUESTION=45
    PLUS=46
    MINUS=47
    STAR=48
    SLASH=49
    PERCENT=50
    PLUSEQUAL=51
    MINEQUAL=52
    STAREQUAL=53
    SLASHEQUAL=54
    PERCENTEQUAL=55
    COLONEQUAL=56
    NAME=57
    NUMBER=58
    STRING=59
    COLOR=60
    NEWLINE=61
    WS=62
    COMMENT=63
    ERROR_TOKEN=64

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class StartContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def start_script(self):
            return self.getTypedRuleContext(PinescriptParser.Start_scriptContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_start

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStart" ):
                return visitor.visitStart(self)
            else:
                return visitor.visitChildren(self)




    def start(self):

        localctx = PinescriptParser.StartContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_start)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 222
            self.start_script()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Start_scriptContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(PinescriptParser.EOF, 0)

        def statements(self):
            return self.getTypedRuleContext(PinescriptParser.StatementsContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_start_script

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStart_script" ):
                return visitor.visitStart_script(self)
            else:
                return visitor.visitChildren(self)




    def start_script(self):

        localctx = PinescriptParser.Start_scriptContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_start_script)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 225
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 2161938933794930080) != 0):
                self.state = 224
                self.statements()


            self.state = 227
            self.match(PinescriptParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Start_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def EOF(self):
            return self.getToken(PinescriptParser.EOF, 0)

        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_start_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStart_expression" ):
                return visitor.visitStart_expression(self)
            else:
                return visitor.visitChildren(self)




    def start_expression(self):

        localctx = PinescriptParser.Start_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_start_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 229
            self.expression()
            self.state = 231
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==61:
                self.state = 230
                self.match(PinescriptParser.NEWLINE)


            self.state = 233
            self.match(PinescriptParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Start_commentsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(PinescriptParser.EOF, 0)

        def comments(self):
            return self.getTypedRuleContext(PinescriptParser.CommentsContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_start_comments

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStart_comments" ):
                return visitor.visitStart_comments(self)
            else:
                return visitor.visitChildren(self)




    def start_comments(self):

        localctx = PinescriptParser.Start_commentsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_start_comments)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 236
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==63:
                self.state = 235
                self.comments()


            self.state = 238
            self.match(PinescriptParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StatementsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.StatementContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.StatementContext,i)


        def getRuleIndex(self):
            return PinescriptParser.RULE_statements

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStatements" ):
                return visitor.visitStatements(self)
            else:
                return visitor.visitChildren(self)




    def statements(self):

        localctx = PinescriptParser.StatementsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_statements)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 241 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 240
                self.statement()
                self.state = 243 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 2161938933794930080) != 0)):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StatementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def compound_statement(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_statementContext,0)


        def simple_statements(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_statementsContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStatement" ):
                return visitor.visitStatement(self)
            else:
                return visitor.visitChildren(self)




    def statement(self):

        localctx = PinescriptParser.StatementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_statement)
        try:
            self.state = 247
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,4,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 245
                self.compound_statement()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 246
                self.simple_statements()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def compound_assignment(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_assignmentContext,0)


        def type_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Type_declarationContext,0)


        def enum_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Enum_declarationContext,0)


        def structure_statement(self):
            return self.getTypedRuleContext(PinescriptParser.Structure_statementContext,0)


        def method_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Method_declarationContext,0)


        def function_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Function_declarationContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_statement" ):
                return visitor.visitCompound_statement(self)
            else:
                return visitor.visitChildren(self)




    def compound_statement(self):

        localctx = PinescriptParser.Compound_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_compound_statement)
        try:
            self.state = 255
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,5,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 249
                self.compound_assignment()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 250
                self.type_declaration()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 251
                self.enum_declaration()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 252
                self.structure_statement()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 253
                self.method_declaration()
                pass

            elif la_ == 6:
                self.enterOuterAlt(localctx, 6)
                self.state = 254
                self.function_declaration()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_statementsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simple_statement(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Simple_statementContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Simple_statementContext,i)


        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_statements

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_statements" ):
                return visitor.visitSimple_statements(self)
            else:
                return visitor.visitChildren(self)




    def simple_statements(self):

        localctx = PinescriptParser.Simple_statementsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_simple_statements)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 257
            self.simple_statement()
            self.state = 262
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,6,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 258
                    self.match(PinescriptParser.COMMA)
                    self.state = 259
                    self.simple_statement() 
                self.state = 264
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,6,self._ctx)

            self.state = 266
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 265
                self.match(PinescriptParser.COMMA)


            self.state = 268
            self.match(PinescriptParser.NEWLINE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simple_assignment(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_assignmentContext,0)


        def expression_statement(self):
            return self.getTypedRuleContext(PinescriptParser.Expression_statementContext,0)


        def import_statement(self):
            return self.getTypedRuleContext(PinescriptParser.Import_statementContext,0)


        def break_statement(self):
            return self.getTypedRuleContext(PinescriptParser.Break_statementContext,0)


        def continue_statement(self):
            return self.getTypedRuleContext(PinescriptParser.Continue_statementContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_statement" ):
                return visitor.visitSimple_statement(self)
            else:
                return visitor.visitChildren(self)




    def simple_statement(self):

        localctx = PinescriptParser.Simple_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_simple_statement)
        try:
            self.state = 275
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 270
                self.simple_assignment()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 271
                self.expression_statement()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 272
                self.import_statement()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 273
                self.break_statement()
                pass

            elif la_ == 5:
                self.enterOuterAlt(localctx, 5)
                self.state = 274
                self.continue_statement()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_assignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def compound_variable_initialization(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_variable_initializationContext,0)


        def compound_reassignment(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_reassignmentContext,0)


        def compound_augassignment(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_augassignmentContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_assignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_assignment" ):
                return visitor.visitCompound_assignment(self)
            else:
                return visitor.visitChildren(self)




    def compound_assignment(self):

        localctx = PinescriptParser.Compound_assignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_compound_assignment)
        try:
            self.state = 280
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 277
                self.compound_variable_initialization()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 278
                self.compound_reassignment()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 279
                self.compound_augassignment()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_variable_initializationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def compound_name_initialization(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_name_initializationContext,0)


        def compound_tuple_initialization(self):
            return self.getTypedRuleContext(PinescriptParser.Compound_tuple_initializationContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_variable_initialization

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_variable_initialization" ):
                return visitor.visitCompound_variable_initialization(self)
            else:
                return visitor.visitChildren(self)




    def compound_variable_initialization(self):

        localctx = PinescriptParser.Compound_variable_initializationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_compound_variable_initialization)
        try:
            self.state = 284
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [7, 10, 17, 18, 21, 22, 25, 27, 28, 57]:
                self.enterOuterAlt(localctx, 1)
                self.state = 282
                self.compound_name_initialization()
                pass
            elif token in [32]:
                self.enterOuterAlt(localctx, 2)
                self.state = 283
                self.compound_tuple_initialization()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_name_initializationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def variable_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Variable_declarationContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def structure_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Structure_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_name_initialization

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_name_initialization" ):
                return visitor.visitCompound_name_initialization(self)
            else:
                return visitor.visitChildren(self)




    def compound_name_initialization(self):

        localctx = PinescriptParser.Compound_name_initializationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_compound_name_initialization)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 286
            self.variable_declaration()
            self.state = 287
            self.match(PinescriptParser.EQUAL)
            self.state = 288
            self.structure_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_tuple_initializationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def tuple_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Tuple_declarationContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def structure_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Structure_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_tuple_initialization

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_tuple_initialization" ):
                return visitor.visitCompound_tuple_initialization(self)
            else:
                return visitor.visitChildren(self)




    def compound_tuple_initialization(self):

        localctx = PinescriptParser.Compound_tuple_initializationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_compound_tuple_initialization)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 290
            self.tuple_declaration()
            self.state = 291
            self.match(PinescriptParser.EQUAL)
            self.state = 292
            self.structure_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_reassignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignment_target(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_targetContext,0)


        def COLONEQUAL(self):
            return self.getToken(PinescriptParser.COLONEQUAL, 0)

        def structure_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Structure_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_reassignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_reassignment" ):
                return visitor.visitCompound_reassignment(self)
            else:
                return visitor.visitChildren(self)




    def compound_reassignment(self):

        localctx = PinescriptParser.Compound_reassignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_compound_reassignment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 294
            self.assignment_target()
            self.state = 295
            self.match(PinescriptParser.COLONEQUAL)
            self.state = 296
            self.structure_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Compound_augassignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignment_target(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_targetContext,0)


        def augassign_op(self):
            return self.getTypedRuleContext(PinescriptParser.Augassign_opContext,0)


        def structure_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Structure_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_compound_augassignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCompound_augassignment" ):
                return visitor.visitCompound_augassignment(self)
            else:
                return visitor.visitChildren(self)




    def compound_augassignment(self):

        localctx = PinescriptParser.Compound_augassignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_compound_augassignment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 298
            self.assignment_target()
            self.state = 299
            self.augassign_op()
            self.state = 300
            self.structure_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Function_declarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name(self):
            return self.getTypedRuleContext(PinescriptParser.NameContext,0)


        def LPAR(self):
            return self.getToken(PinescriptParser.LPAR, 0)

        def RPAR(self):
            return self.getToken(PinescriptParser.RPAR, 0)

        def RARROW(self):
            return self.getToken(PinescriptParser.RARROW, 0)

        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def EXPORT(self):
            return self.getToken(PinescriptParser.EXPORT, 0)

        def parameter_list(self):
            return self.getTypedRuleContext(PinescriptParser.Parameter_listContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_function_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunction_declaration" ):
                return visitor.visitFunction_declaration(self)
            else:
                return visitor.visitChildren(self)




    def function_declaration(self):

        localctx = PinescriptParser.Function_declarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_function_declaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 303
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 302
                self.match(PinescriptParser.EXPORT)


            self.state = 305
            self.name()
            self.state = 306
            self.match(PinescriptParser.LPAR)
            self.state = 308
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 144115188116096128) != 0):
                self.state = 307
                self.parameter_list()


            self.state = 310
            self.match(PinescriptParser.RPAR)
            self.state = 311
            self.match(PinescriptParser.RARROW)
            self.state = 312
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Parameter_listContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def parameter_definition(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Parameter_definitionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Parameter_definitionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_parameter_list

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParameter_list" ):
                return visitor.visitParameter_list(self)
            else:
                return visitor.visitChildren(self)




    def parameter_list(self):

        localctx = PinescriptParser.Parameter_listContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_parameter_list)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 314
            self.parameter_definition()
            self.state = 319
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,13,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 315
                    self.match(PinescriptParser.COMMA)
                    self.state = 316
                    self.parameter_definition() 
                self.state = 321
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,13,self._ctx)

            self.state = 323
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 322
                self.match(PinescriptParser.COMMA)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Parameter_definitionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def type_specification(self):
            return self.getTypedRuleContext(PinescriptParser.Type_specificationContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_parameter_definition

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitParameter_definition" ):
                return visitor.visitParameter_definition(self)
            else:
                return visitor.visitChildren(self)




    def parameter_definition(self):

        localctx = PinescriptParser.Parameter_definitionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_parameter_definition)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 326
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,15,self._ctx)
            if la_ == 1:
                self.state = 325
                self.type_specification()


            self.state = 328
            self.name_store()
            self.state = 331
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==36:
                self.state = 329
                self.match(PinescriptParser.EQUAL)
                self.state = 330
                self.expression()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Method_declarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def METHOD(self):
            return self.getToken(PinescriptParser.METHOD, 0)

        def name(self):
            return self.getTypedRuleContext(PinescriptParser.NameContext,0)


        def LPAR(self):
            return self.getToken(PinescriptParser.LPAR, 0)

        def RPAR(self):
            return self.getToken(PinescriptParser.RPAR, 0)

        def RARROW(self):
            return self.getToken(PinescriptParser.RARROW, 0)

        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def EXPORT(self):
            return self.getToken(PinescriptParser.EXPORT, 0)

        def method_parameter_list(self):
            return self.getTypedRuleContext(PinescriptParser.Method_parameter_listContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_method_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMethod_declaration" ):
                return visitor.visitMethod_declaration(self)
            else:
                return visitor.visitChildren(self)




    def method_declaration(self):

        localctx = PinescriptParser.Method_declarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 36, self.RULE_method_declaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 334
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 333
                self.match(PinescriptParser.EXPORT)


            self.state = 336
            self.match(PinescriptParser.METHOD)
            self.state = 337
            self.name()
            self.state = 338
            self.match(PinescriptParser.LPAR)
            self.state = 340
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 144115188116096128) != 0):
                self.state = 339
                self.method_parameter_list()


            self.state = 342
            self.match(PinescriptParser.RPAR)
            self.state = 343
            self.match(PinescriptParser.RARROW)
            self.state = 344
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Method_parameter_listContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def method_parameter_definition(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Method_parameter_definitionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Method_parameter_definitionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_method_parameter_list

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMethod_parameter_list" ):
                return visitor.visitMethod_parameter_list(self)
            else:
                return visitor.visitChildren(self)




    def method_parameter_list(self):

        localctx = PinescriptParser.Method_parameter_listContext(self, self._ctx, self.state)
        self.enterRule(localctx, 38, self.RULE_method_parameter_list)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 346
            self.method_parameter_definition()
            self.state = 351
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,19,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 347
                    self.match(PinescriptParser.COMMA)
                    self.state = 348
                    self.method_parameter_definition() 
                self.state = 353
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,19,self._ctx)

            self.state = 355
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 354
                self.match(PinescriptParser.COMMA)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Method_parameter_definitionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def type_specification(self):
            return self.getTypedRuleContext(PinescriptParser.Type_specificationContext,0)


        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def parameter_definition(self):
            return self.getTypedRuleContext(PinescriptParser.Parameter_definitionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_method_parameter_definition

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMethod_parameter_definition" ):
                return visitor.visitMethod_parameter_definition(self)
            else:
                return visitor.visitChildren(self)




    def method_parameter_definition(self):

        localctx = PinescriptParser.Method_parameter_definitionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 40, self.RULE_method_parameter_definition)
        try:
            self.state = 361
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,21,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 357
                self.type_specification()
                self.state = 358
                self.name_store()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 360
                self.parameter_definition()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Type_declarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TYPE(self):
            return self.getToken(PinescriptParser.TYPE, 0)

        def name(self):
            return self.getTypedRuleContext(PinescriptParser.NameContext,0)


        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def INDENT(self):
            return self.getToken(PinescriptParser.INDENT, 0)

        def field_definitions(self):
            return self.getTypedRuleContext(PinescriptParser.Field_definitionsContext,0)


        def DEDENT(self):
            return self.getToken(PinescriptParser.DEDENT, 0)

        def EXPORT(self):
            return self.getToken(PinescriptParser.EXPORT, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_type_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitType_declaration" ):
                return visitor.visitType_declaration(self)
            else:
                return visitor.visitChildren(self)




    def type_declaration(self):

        localctx = PinescriptParser.Type_declarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 42, self.RULE_type_declaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 364
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 363
                self.match(PinescriptParser.EXPORT)


            self.state = 366
            self.match(PinescriptParser.TYPE)
            self.state = 367
            self.name()
            self.state = 368
            self.match(PinescriptParser.NEWLINE)
            self.state = 369
            self.match(PinescriptParser.INDENT)
            self.state = 370
            self.field_definitions()
            self.state = 371
            self.match(PinescriptParser.DEDENT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Field_definitionsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def field_definition(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Field_definitionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Field_definitionContext,i)


        def getRuleIndex(self):
            return PinescriptParser.RULE_field_definitions

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitField_definitions" ):
                return visitor.visitField_definitions(self)
            else:
                return visitor.visitChildren(self)




    def field_definitions(self):

        localctx = PinescriptParser.Field_definitionsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 44, self.RULE_field_definitions)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 374 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 373
                self.field_definition()
                self.state = 376 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 144115188384531584) != 0)):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Field_definitionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def type_specification(self):
            return self.getTypedRuleContext(PinescriptParser.Type_specificationContext,0)


        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def VARIP(self):
            return self.getToken(PinescriptParser.VARIP, 0)

        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_field_definition

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitField_definition" ):
                return visitor.visitField_definition(self)
            else:
                return visitor.visitChildren(self)




    def field_definition(self):

        localctx = PinescriptParser.Field_definitionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 46, self.RULE_field_definition)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 379
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==28:
                self.state = 378
                self.match(PinescriptParser.VARIP)


            self.state = 381
            self.type_specification()
            self.state = 382
            self.name_store()
            self.state = 385
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==36:
                self.state = 383
                self.match(PinescriptParser.EQUAL)
                self.state = 384
                self.expression()


            self.state = 387
            self.match(PinescriptParser.NEWLINE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Enum_declarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ENUM(self):
            return self.getToken(PinescriptParser.ENUM, 0)

        def name(self):
            return self.getTypedRuleContext(PinescriptParser.NameContext,0)


        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def INDENT(self):
            return self.getToken(PinescriptParser.INDENT, 0)

        def enum_definitions(self):
            return self.getTypedRuleContext(PinescriptParser.Enum_definitionsContext,0)


        def DEDENT(self):
            return self.getToken(PinescriptParser.DEDENT, 0)

        def EXPORT(self):
            return self.getToken(PinescriptParser.EXPORT, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_enum_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEnum_declaration" ):
                return visitor.visitEnum_declaration(self)
            else:
                return visitor.visitChildren(self)




    def enum_declaration(self):

        localctx = PinescriptParser.Enum_declarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 48, self.RULE_enum_declaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 390
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==11:
                self.state = 389
                self.match(PinescriptParser.EXPORT)


            self.state = 392
            self.match(PinescriptParser.ENUM)
            self.state = 393
            self.name()
            self.state = 394
            self.match(PinescriptParser.NEWLINE)
            self.state = 395
            self.match(PinescriptParser.INDENT)
            self.state = 396
            self.enum_definitions()
            self.state = 397
            self.match(PinescriptParser.DEDENT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Enum_definitionsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def enum_definition(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Enum_definitionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Enum_definitionContext,i)


        def getRuleIndex(self):
            return PinescriptParser.RULE_enum_definitions

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEnum_definitions" ):
                return visitor.visitEnum_definitions(self)
            else:
                return visitor.visitChildren(self)




    def enum_definitions(self):

        localctx = PinescriptParser.Enum_definitionsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 50, self.RULE_enum_definitions)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 400 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 399
                self.enum_definition()
                self.state = 402 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 144115188116096128) != 0)):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Enum_definitionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_enum_definition

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEnum_definition" ):
                return visitor.visitEnum_definition(self)
            else:
                return visitor.visitChildren(self)




    def enum_definition(self):

        localctx = PinescriptParser.Enum_definitionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 52, self.RULE_enum_definition)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 404
            self.name_store()
            self.state = 407
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==36:
                self.state = 405
                self.match(PinescriptParser.EQUAL)
                self.state = 406
                self.expression()


            self.state = 409
            self.match(PinescriptParser.NEWLINE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class StructureContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def if_structure(self):
            return self.getTypedRuleContext(PinescriptParser.If_structureContext,0)


        def for_structure(self):
            return self.getTypedRuleContext(PinescriptParser.For_structureContext,0)


        def while_structure(self):
            return self.getTypedRuleContext(PinescriptParser.While_structureContext,0)


        def switch_structure(self):
            return self.getTypedRuleContext(PinescriptParser.Switch_structureContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_structure

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructure" ):
                return visitor.visitStructure(self)
            else:
                return visitor.visitChildren(self)




    def structure(self):

        localctx = PinescriptParser.StructureContext(self, self._ctx, self.state)
        self.enterRule(localctx, 54, self.RULE_structure)
        try:
            self.state = 415
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [14]:
                self.enterOuterAlt(localctx, 1)
                self.state = 411
                self.if_structure()
                pass
            elif token in [13]:
                self.enterOuterAlt(localctx, 2)
                self.state = 412
                self.for_structure()
                pass
            elif token in [29]:
                self.enterOuterAlt(localctx, 3)
                self.state = 413
                self.while_structure()
                pass
            elif token in [23]:
                self.enterOuterAlt(localctx, 4)
                self.state = 414
                self.switch_structure()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Structure_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def structure(self):
            return self.getTypedRuleContext(PinescriptParser.StructureContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_structure_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructure_statement" ):
                return visitor.visitStructure_statement(self)
            else:
                return visitor.visitChildren(self)




    def structure_statement(self):

        localctx = PinescriptParser.Structure_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 56, self.RULE_structure_statement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 417
            self.structure()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Structure_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def structure(self):
            return self.getTypedRuleContext(PinescriptParser.StructureContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_structure_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStructure_expression" ):
                return visitor.visitStructure_expression(self)
            else:
                return visitor.visitChildren(self)




    def structure_expression(self):

        localctx = PinescriptParser.Structure_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 58, self.RULE_structure_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 419
            self.structure()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class If_structureContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def if_structure_elif(self):
            return self.getTypedRuleContext(PinescriptParser.If_structure_elifContext,0)


        def if_structure_else(self):
            return self.getTypedRuleContext(PinescriptParser.If_structure_elseContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_if_structure

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIf_structure" ):
                return visitor.visitIf_structure(self)
            else:
                return visitor.visitChildren(self)




    def if_structure(self):

        localctx = PinescriptParser.If_structureContext(self, self._ctx, self.state)
        self.enterRule(localctx, 60, self.RULE_if_structure)
        try:
            self.state = 423
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,30,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 421
                self.if_structure_elif()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 422
                self.if_structure_else()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class If_structure_elifContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IF(self):
            return self.getToken(PinescriptParser.IF, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def elif_structure(self):
            return self.getTypedRuleContext(PinescriptParser.Elif_structureContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_if_structure_elif

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIf_structure_elif" ):
                return visitor.visitIf_structure_elif(self)
            else:
                return visitor.visitChildren(self)




    def if_structure_elif(self):

        localctx = PinescriptParser.If_structure_elifContext(self, self._ctx, self.state)
        self.enterRule(localctx, 62, self.RULE_if_structure_elif)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 425
            self.match(PinescriptParser.IF)
            self.state = 426
            self.expression()
            self.state = 427
            self.local_block()
            self.state = 428
            self.elif_structure()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class If_structure_elseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IF(self):
            return self.getToken(PinescriptParser.IF, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def else_block(self):
            return self.getTypedRuleContext(PinescriptParser.Else_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_if_structure_else

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIf_structure_else" ):
                return visitor.visitIf_structure_else(self)
            else:
                return visitor.visitChildren(self)




    def if_structure_else(self):

        localctx = PinescriptParser.If_structure_elseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 64, self.RULE_if_structure_else)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 430
            self.match(PinescriptParser.IF)
            self.state = 431
            self.expression()
            self.state = 432
            self.local_block()
            self.state = 434
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,31,self._ctx)
            if la_ == 1:
                self.state = 433
                self.else_block()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Elif_structureContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def elif_structure_elif(self):
            return self.getTypedRuleContext(PinescriptParser.Elif_structure_elifContext,0)


        def elif_structure_else(self):
            return self.getTypedRuleContext(PinescriptParser.Elif_structure_elseContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_elif_structure

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitElif_structure" ):
                return visitor.visitElif_structure(self)
            else:
                return visitor.visitChildren(self)




    def elif_structure(self):

        localctx = PinescriptParser.Elif_structureContext(self, self._ctx, self.state)
        self.enterRule(localctx, 66, self.RULE_elif_structure)
        try:
            self.state = 438
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,32,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 436
                self.elif_structure_elif()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 437
                self.elif_structure_else()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Elif_structure_elifContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ELSE(self):
            return self.getToken(PinescriptParser.ELSE, 0)

        def IF(self):
            return self.getToken(PinescriptParser.IF, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def elif_structure(self):
            return self.getTypedRuleContext(PinescriptParser.Elif_structureContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_elif_structure_elif

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitElif_structure_elif" ):
                return visitor.visitElif_structure_elif(self)
            else:
                return visitor.visitChildren(self)




    def elif_structure_elif(self):

        localctx = PinescriptParser.Elif_structure_elifContext(self, self._ctx, self.state)
        self.enterRule(localctx, 68, self.RULE_elif_structure_elif)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 440
            self.match(PinescriptParser.ELSE)
            self.state = 441
            self.match(PinescriptParser.IF)
            self.state = 442
            self.expression()
            self.state = 443
            self.local_block()
            self.state = 444
            self.elif_structure()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Elif_structure_elseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ELSE(self):
            return self.getToken(PinescriptParser.ELSE, 0)

        def IF(self):
            return self.getToken(PinescriptParser.IF, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def else_block(self):
            return self.getTypedRuleContext(PinescriptParser.Else_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_elif_structure_else

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitElif_structure_else" ):
                return visitor.visitElif_structure_else(self)
            else:
                return visitor.visitChildren(self)




    def elif_structure_else(self):

        localctx = PinescriptParser.Elif_structure_elseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 70, self.RULE_elif_structure_else)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 446
            self.match(PinescriptParser.ELSE)
            self.state = 447
            self.match(PinescriptParser.IF)
            self.state = 448
            self.expression()
            self.state = 449
            self.local_block()
            self.state = 451
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,33,self._ctx)
            if la_ == 1:
                self.state = 450
                self.else_block()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Else_blockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def ELSE(self):
            return self.getToken(PinescriptParser.ELSE, 0)

        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_else_block

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitElse_block" ):
                return visitor.visitElse_block(self)
            else:
                return visitor.visitChildren(self)




    def else_block(self):

        localctx = PinescriptParser.Else_blockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 72, self.RULE_else_block)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 453
            self.match(PinescriptParser.ELSE)
            self.state = 454
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class For_structureContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def for_structure_to(self):
            return self.getTypedRuleContext(PinescriptParser.For_structure_toContext,0)


        def for_structure_in(self):
            return self.getTypedRuleContext(PinescriptParser.For_structure_inContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_for_structure

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFor_structure" ):
                return visitor.visitFor_structure(self)
            else:
                return visitor.visitChildren(self)




    def for_structure(self):

        localctx = PinescriptParser.For_structureContext(self, self._ctx, self.state)
        self.enterRule(localctx, 74, self.RULE_for_structure)
        try:
            self.state = 458
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,34,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 456
                self.for_structure_to()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 457
                self.for_structure_in()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class For_structure_toContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def FOR(self):
            return self.getToken(PinescriptParser.FOR, 0)

        def for_iterator(self):
            return self.getTypedRuleContext(PinescriptParser.For_iteratorContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.ExpressionContext,i)


        def TO(self):
            return self.getToken(PinescriptParser.TO, 0)

        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def BY(self):
            return self.getToken(PinescriptParser.BY, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_for_structure_to

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFor_structure_to" ):
                return visitor.visitFor_structure_to(self)
            else:
                return visitor.visitChildren(self)




    def for_structure_to(self):

        localctx = PinescriptParser.For_structure_toContext(self, self._ctx, self.state)
        self.enterRule(localctx, 76, self.RULE_for_structure_to)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 460
            self.match(PinescriptParser.FOR)
            self.state = 461
            self.for_iterator()
            self.state = 462
            self.match(PinescriptParser.EQUAL)
            self.state = 463
            self.expression()
            self.state = 464
            self.match(PinescriptParser.TO)
            self.state = 465
            self.expression()
            self.state = 468
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==6:
                self.state = 466
                self.match(PinescriptParser.BY)
                self.state = 467
                self.expression()


            self.state = 470
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class For_structure_inContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def FOR(self):
            return self.getToken(PinescriptParser.FOR, 0)

        def for_iterator(self):
            return self.getTypedRuleContext(PinescriptParser.For_iteratorContext,0)


        def IN(self):
            return self.getToken(PinescriptParser.IN, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_for_structure_in

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFor_structure_in" ):
                return visitor.visitFor_structure_in(self)
            else:
                return visitor.visitChildren(self)




    def for_structure_in(self):

        localctx = PinescriptParser.For_structure_inContext(self, self._ctx, self.state)
        self.enterRule(localctx, 78, self.RULE_for_structure_in)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 472
            self.match(PinescriptParser.FOR)
            self.state = 473
            self.for_iterator()
            self.state = 474
            self.match(PinescriptParser.IN)
            self.state = 475
            self.expression()
            self.state = 476
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class For_iteratorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def tuple_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Tuple_declarationContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_for_iterator

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFor_iterator" ):
                return visitor.visitFor_iterator(self)
            else:
                return visitor.visitChildren(self)




    def for_iterator(self):

        localctx = PinescriptParser.For_iteratorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 80, self.RULE_for_iterator)
        try:
            self.state = 480
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [7, 10, 17, 18, 21, 22, 25, 57]:
                self.enterOuterAlt(localctx, 1)
                self.state = 478
                self.name_store()
                pass
            elif token in [32]:
                self.enterOuterAlt(localctx, 2)
                self.state = 479
                self.tuple_declaration()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class While_structureContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def WHILE(self):
            return self.getToken(PinescriptParser.WHILE, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_while_structure

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitWhile_structure" ):
                return visitor.visitWhile_structure(self)
            else:
                return visitor.visitChildren(self)




    def while_structure(self):

        localctx = PinescriptParser.While_structureContext(self, self._ctx, self.state)
        self.enterRule(localctx, 82, self.RULE_while_structure)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 482
            self.match(PinescriptParser.WHILE)
            self.state = 483
            self.expression()
            self.state = 484
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Switch_structureContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SWITCH(self):
            return self.getToken(PinescriptParser.SWITCH, 0)

        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def INDENT(self):
            return self.getToken(PinescriptParser.INDENT, 0)

        def switch_cases(self):
            return self.getTypedRuleContext(PinescriptParser.Switch_casesContext,0)


        def DEDENT(self):
            return self.getToken(PinescriptParser.DEDENT, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_switch_structure

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSwitch_structure" ):
                return visitor.visitSwitch_structure(self)
            else:
                return visitor.visitChildren(self)




    def switch_structure(self):

        localctx = PinescriptParser.Switch_structureContext(self, self._ctx, self.state)
        self.enterRule(localctx, 84, self.RULE_switch_structure)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 486
            self.match(PinescriptParser.SWITCH)
            self.state = 488
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 2161938932846957696) != 0):
                self.state = 487
                self.expression()


            self.state = 490
            self.match(PinescriptParser.NEWLINE)
            self.state = 491
            self.match(PinescriptParser.INDENT)
            self.state = 492
            self.switch_cases()
            self.state = 493
            self.match(PinescriptParser.DEDENT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Switch_casesContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def switch_pattern_case(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Switch_pattern_caseContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Switch_pattern_caseContext,i)


        def switch_default_case(self):
            return self.getTypedRuleContext(PinescriptParser.Switch_default_caseContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_switch_cases

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSwitch_cases" ):
                return visitor.visitSwitch_cases(self)
            else:
                return visitor.visitChildren(self)




    def switch_cases(self):

        localctx = PinescriptParser.Switch_casesContext(self, self._ctx, self.state)
        self.enterRule(localctx, 86, self.RULE_switch_cases)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 496 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 495
                self.switch_pattern_case()
                self.state = 498 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not ((((_la) & ~0x3f) == 0 and ((1 << _la) & 2161938932846957696) != 0)):
                    break

            self.state = 501
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==41:
                self.state = 500
                self.switch_default_case()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Switch_pattern_caseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def RARROW(self):
            return self.getToken(PinescriptParser.RARROW, 0)

        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_switch_pattern_case

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSwitch_pattern_case" ):
                return visitor.visitSwitch_pattern_case(self)
            else:
                return visitor.visitChildren(self)




    def switch_pattern_case(self):

        localctx = PinescriptParser.Switch_pattern_caseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 88, self.RULE_switch_pattern_case)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 503
            self.expression()
            self.state = 504
            self.match(PinescriptParser.RARROW)
            self.state = 505
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Switch_default_caseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def RARROW(self):
            return self.getToken(PinescriptParser.RARROW, 0)

        def local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Local_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_switch_default_case

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSwitch_default_case" ):
                return visitor.visitSwitch_default_case(self)
            else:
                return visitor.visitChildren(self)




    def switch_default_case(self):

        localctx = PinescriptParser.Switch_default_caseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 90, self.RULE_switch_default_case)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 507
            self.match(PinescriptParser.RARROW)
            self.state = 508
            self.local_block()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Local_blockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def indented_local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Indented_local_blockContext,0)


        def inline_local_block(self):
            return self.getTypedRuleContext(PinescriptParser.Inline_local_blockContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_local_block

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLocal_block" ):
                return visitor.visitLocal_block(self)
            else:
                return visitor.visitChildren(self)




    def local_block(self):

        localctx = PinescriptParser.Local_blockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 92, self.RULE_local_block)
        try:
            self.state = 512
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [61]:
                self.enterOuterAlt(localctx, 1)
                self.state = 510
                self.indented_local_block()
                pass
            elif token in [5, 7, 8, 10, 11, 12, 13, 14, 15, 17, 18, 19, 21, 22, 23, 25, 26, 27, 28, 29, 30, 32, 46, 47, 57, 58, 59, 60]:
                self.enterOuterAlt(localctx, 2)
                self.state = 511
                self.inline_local_block()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Indented_local_blockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NEWLINE(self):
            return self.getToken(PinescriptParser.NEWLINE, 0)

        def INDENT(self):
            return self.getToken(PinescriptParser.INDENT, 0)

        def statements(self):
            return self.getTypedRuleContext(PinescriptParser.StatementsContext,0)


        def DEDENT(self):
            return self.getToken(PinescriptParser.DEDENT, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_indented_local_block

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitIndented_local_block" ):
                return visitor.visitIndented_local_block(self)
            else:
                return visitor.visitChildren(self)




    def indented_local_block(self):

        localctx = PinescriptParser.Indented_local_blockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 94, self.RULE_indented_local_block)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 514
            self.match(PinescriptParser.NEWLINE)
            self.state = 515
            self.match(PinescriptParser.INDENT)
            self.state = 516
            self.statements()
            self.state = 517
            self.match(PinescriptParser.DEDENT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Inline_local_blockContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def statement(self):
            return self.getTypedRuleContext(PinescriptParser.StatementContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_inline_local_block

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInline_local_block" ):
                return visitor.visitInline_local_block(self)
            else:
                return visitor.visitChildren(self)




    def inline_local_block(self):

        localctx = PinescriptParser.Inline_local_blockContext(self, self._ctx, self.state)
        self.enterRule(localctx, 96, self.RULE_inline_local_block)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 519
            self.statement()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_assignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simple_variable_initialization(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_variable_initializationContext,0)


        def simple_reassignment(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_reassignmentContext,0)


        def simple_augassignment(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_augassignmentContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_assignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_assignment" ):
                return visitor.visitSimple_assignment(self)
            else:
                return visitor.visitChildren(self)




    def simple_assignment(self):

        localctx = PinescriptParser.Simple_assignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 98, self.RULE_simple_assignment)
        try:
            self.state = 524
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,41,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 521
                self.simple_variable_initialization()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 522
                self.simple_reassignment()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 523
                self.simple_augassignment()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_variable_initializationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def simple_name_initialization(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_name_initializationContext,0)


        def simple_tuple_initialization(self):
            return self.getTypedRuleContext(PinescriptParser.Simple_tuple_initializationContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_variable_initialization

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_variable_initialization" ):
                return visitor.visitSimple_variable_initialization(self)
            else:
                return visitor.visitChildren(self)




    def simple_variable_initialization(self):

        localctx = PinescriptParser.Simple_variable_initializationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 100, self.RULE_simple_variable_initialization)
        try:
            self.state = 528
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [7, 10, 17, 18, 21, 22, 25, 27, 28, 57]:
                self.enterOuterAlt(localctx, 1)
                self.state = 526
                self.simple_name_initialization()
                pass
            elif token in [32]:
                self.enterOuterAlt(localctx, 2)
                self.state = 527
                self.simple_tuple_initialization()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_name_initializationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def variable_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Variable_declarationContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_name_initialization

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_name_initialization" ):
                return visitor.visitSimple_name_initialization(self)
            else:
                return visitor.visitChildren(self)




    def simple_name_initialization(self):

        localctx = PinescriptParser.Simple_name_initializationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 102, self.RULE_simple_name_initialization)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 530
            self.variable_declaration()
            self.state = 531
            self.match(PinescriptParser.EQUAL)
            self.state = 532
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_tuple_initializationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def tuple_declaration(self):
            return self.getTypedRuleContext(PinescriptParser.Tuple_declarationContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_tuple_initialization

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_tuple_initialization" ):
                return visitor.visitSimple_tuple_initialization(self)
            else:
                return visitor.visitChildren(self)




    def simple_tuple_initialization(self):

        localctx = PinescriptParser.Simple_tuple_initializationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 104, self.RULE_simple_tuple_initialization)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 534
            self.tuple_declaration()
            self.state = 535
            self.match(PinescriptParser.EQUAL)
            self.state = 536
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_reassignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignment_target(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_targetContext,0)


        def COLONEQUAL(self):
            return self.getToken(PinescriptParser.COLONEQUAL, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_reassignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_reassignment" ):
                return visitor.visitSimple_reassignment(self)
            else:
                return visitor.visitChildren(self)




    def simple_reassignment(self):

        localctx = PinescriptParser.Simple_reassignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 106, self.RULE_simple_reassignment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 538
            self.assignment_target()
            self.state = 539
            self.match(PinescriptParser.COLONEQUAL)
            self.state = 540
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Simple_augassignmentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignment_target(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_targetContext,0)


        def augassign_op(self):
            return self.getTypedRuleContext(PinescriptParser.Augassign_opContext,0)


        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_simple_augassignment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSimple_augassignment" ):
                return visitor.visitSimple_augassignment(self)
            else:
                return visitor.visitChildren(self)




    def simple_augassignment(self):

        localctx = PinescriptParser.Simple_augassignmentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 108, self.RULE_simple_augassignment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 542
            self.assignment_target()
            self.state = 543
            self.augassign_op()
            self.state = 544
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def conditional_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Conditional_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpression" ):
                return visitor.visitExpression(self)
            else:
                return visitor.visitChildren(self)




    def expression(self):

        localctx = PinescriptParser.ExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 110, self.RULE_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 546
            self.conditional_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Expression_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_expression_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitExpression_statement" ):
                return visitor.visitExpression_statement(self)
            else:
                return visitor.visitChildren(self)




    def expression_statement(self):

        localctx = PinescriptParser.Expression_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 112, self.RULE_expression_statement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 548
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Conditional_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def disjunction_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Disjunction_expressionContext,0)


        def QUESTION(self):
            return self.getToken(PinescriptParser.QUESTION, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.ExpressionContext,i)


        def COLON(self):
            return self.getToken(PinescriptParser.COLON, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_conditional_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitConditional_expression" ):
                return visitor.visitConditional_expression(self)
            else:
                return visitor.visitChildren(self)




    def conditional_expression(self):

        localctx = PinescriptParser.Conditional_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 114, self.RULE_conditional_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 550
            self.disjunction_expression()
            self.state = 556
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==45:
                self.state = 551
                self.match(PinescriptParser.QUESTION)
                self.state = 552
                self.expression()
                self.state = 553
                self.match(PinescriptParser.COLON)
                self.state = 554
                self.expression()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Disjunction_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def conjunction_expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Conjunction_expressionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Conjunction_expressionContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.OR)
            else:
                return self.getToken(PinescriptParser.OR, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_disjunction_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDisjunction_expression" ):
                return visitor.visitDisjunction_expression(self)
            else:
                return visitor.visitChildren(self)




    def disjunction_expression(self):

        localctx = PinescriptParser.Disjunction_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 116, self.RULE_disjunction_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 558
            self.conjunction_expression()
            self.state = 563
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==20:
                self.state = 559
                self.match(PinescriptParser.OR)
                self.state = 560
                self.conjunction_expression()
                self.state = 565
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Conjunction_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def equality_expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Equality_expressionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Equality_expressionContext,i)


        def AND(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.AND)
            else:
                return self.getToken(PinescriptParser.AND, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_conjunction_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitConjunction_expression" ):
                return visitor.visitConjunction_expression(self)
            else:
                return visitor.visitChildren(self)




    def conjunction_expression(self):

        localctx = PinescriptParser.Conjunction_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 118, self.RULE_conjunction_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 566
            self.equality_expression()
            self.state = 571
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==3:
                self.state = 567
                self.match(PinescriptParser.AND)
                self.state = 568
                self.equality_expression()
                self.state = 573
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Equality_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def inequality_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Inequality_expressionContext,0)


        def equality_trailing_pair(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Equality_trailing_pairContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Equality_trailing_pairContext,i)


        def getRuleIndex(self):
            return PinescriptParser.RULE_equality_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEquality_expression" ):
                return visitor.visitEquality_expression(self)
            else:
                return visitor.visitChildren(self)




    def equality_expression(self):

        localctx = PinescriptParser.Equality_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 120, self.RULE_equality_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 574
            self.inequality_expression()
            self.state = 578
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==37 or _la==38:
                self.state = 575
                self.equality_trailing_pair()
                self.state = 580
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Equality_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def equal_trailing_pair(self):
            return self.getTypedRuleContext(PinescriptParser.Equal_trailing_pairContext,0)


        def not_equal_trailing_pair(self):
            return self.getTypedRuleContext(PinescriptParser.Not_equal_trailing_pairContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_equality_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEquality_trailing_pair" ):
                return visitor.visitEquality_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def equality_trailing_pair(self):

        localctx = PinescriptParser.Equality_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 122, self.RULE_equality_trailing_pair)
        try:
            self.state = 583
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [37]:
                self.enterOuterAlt(localctx, 1)
                self.state = 581
                self.equal_trailing_pair()
                pass
            elif token in [38]:
                self.enterOuterAlt(localctx, 2)
                self.state = 582
                self.not_equal_trailing_pair()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Equal_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EQEQUAL(self):
            return self.getToken(PinescriptParser.EQEQUAL, 0)

        def inequality_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Inequality_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_equal_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEqual_trailing_pair" ):
                return visitor.visitEqual_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def equal_trailing_pair(self):

        localctx = PinescriptParser.Equal_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 124, self.RULE_equal_trailing_pair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 585
            self.match(PinescriptParser.EQEQUAL)
            self.state = 586
            self.inequality_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Not_equal_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NOTEQUAL(self):
            return self.getToken(PinescriptParser.NOTEQUAL, 0)

        def inequality_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Inequality_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_not_equal_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNot_equal_trailing_pair" ):
                return visitor.visitNot_equal_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def not_equal_trailing_pair(self):

        localctx = PinescriptParser.Not_equal_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 126, self.RULE_not_equal_trailing_pair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 588
            self.match(PinescriptParser.NOTEQUAL)
            self.state = 589
            self.inequality_expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Inequality_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def additive_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_expressionContext,0)


        def inequality_trailing_pair(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Inequality_trailing_pairContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Inequality_trailing_pairContext,i)


        def getRuleIndex(self):
            return PinescriptParser.RULE_inequality_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInequality_expression" ):
                return visitor.visitInequality_expression(self)
            else:
                return visitor.visitChildren(self)




    def inequality_expression(self):

        localctx = PinescriptParser.Inequality_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 128, self.RULE_inequality_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 591
            self.additive_expression(0)
            self.state = 595
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & 1700807049216) != 0):
                self.state = 592
                self.inequality_trailing_pair()
                self.state = 597
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Inequality_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def less_than_equal_trailing_pair(self):
            return self.getTypedRuleContext(PinescriptParser.Less_than_equal_trailing_pairContext,0)


        def less_than_trailing_pair(self):
            return self.getTypedRuleContext(PinescriptParser.Less_than_trailing_pairContext,0)


        def greater_than_equal_trailing_pair(self):
            return self.getTypedRuleContext(PinescriptParser.Greater_than_equal_trailing_pairContext,0)


        def greater_than_trailing_pair(self):
            return self.getTypedRuleContext(PinescriptParser.Greater_than_trailing_pairContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_inequality_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitInequality_trailing_pair" ):
                return visitor.visitInequality_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def inequality_trailing_pair(self):

        localctx = PinescriptParser.Inequality_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 130, self.RULE_inequality_trailing_pair)
        try:
            self.state = 602
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [39]:
                self.enterOuterAlt(localctx, 1)
                self.state = 598
                self.less_than_equal_trailing_pair()
                pass
            elif token in [34]:
                self.enterOuterAlt(localctx, 2)
                self.state = 599
                self.less_than_trailing_pair()
                pass
            elif token in [40]:
                self.enterOuterAlt(localctx, 3)
                self.state = 600
                self.greater_than_equal_trailing_pair()
                pass
            elif token in [35]:
                self.enterOuterAlt(localctx, 4)
                self.state = 601
                self.greater_than_trailing_pair()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Less_than_equal_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LESSEQUAL(self):
            return self.getToken(PinescriptParser.LESSEQUAL, 0)

        def additive_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_less_than_equal_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLess_than_equal_trailing_pair" ):
                return visitor.visitLess_than_equal_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def less_than_equal_trailing_pair(self):

        localctx = PinescriptParser.Less_than_equal_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 132, self.RULE_less_than_equal_trailing_pair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 604
            self.match(PinescriptParser.LESSEQUAL)
            self.state = 605
            self.additive_expression(0)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Less_than_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LESS(self):
            return self.getToken(PinescriptParser.LESS, 0)

        def additive_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_less_than_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLess_than_trailing_pair" ):
                return visitor.visitLess_than_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def less_than_trailing_pair(self):

        localctx = PinescriptParser.Less_than_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 134, self.RULE_less_than_trailing_pair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 607
            self.match(PinescriptParser.LESS)
            self.state = 608
            self.additive_expression(0)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Greater_than_equal_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def GREATEREQUAL(self):
            return self.getToken(PinescriptParser.GREATEREQUAL, 0)

        def additive_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_greater_than_equal_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitGreater_than_equal_trailing_pair" ):
                return visitor.visitGreater_than_equal_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def greater_than_equal_trailing_pair(self):

        localctx = PinescriptParser.Greater_than_equal_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 136, self.RULE_greater_than_equal_trailing_pair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 610
            self.match(PinescriptParser.GREATEREQUAL)
            self.state = 611
            self.additive_expression(0)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Greater_than_trailing_pairContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def GREATER(self):
            return self.getToken(PinescriptParser.GREATER, 0)

        def additive_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_greater_than_trailing_pair

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitGreater_than_trailing_pair" ):
                return visitor.visitGreater_than_trailing_pair(self)
            else:
                return visitor.visitChildren(self)




    def greater_than_trailing_pair(self):

        localctx = PinescriptParser.Greater_than_trailing_pairContext(self, self._ctx, self.state)
        self.enterRule(localctx, 138, self.RULE_greater_than_trailing_pair)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 613
            self.match(PinescriptParser.GREATER)
            self.state = 614
            self.additive_expression(0)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Additive_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def multiplicative_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Multiplicative_expressionContext,0)


        def additive_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_expressionContext,0)


        def additive_op(self):
            return self.getTypedRuleContext(PinescriptParser.Additive_opContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_additive_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAdditive_expression" ):
                return visitor.visitAdditive_expression(self)
            else:
                return visitor.visitChildren(self)



    def additive_expression(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = PinescriptParser.Additive_expressionContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 140
        self.enterRecursionRule(localctx, 140, self.RULE_additive_expression, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 617
            self.multiplicative_expression(0)
            self._ctx.stop = self._input.LT(-1)
            self.state = 625
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,50,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    localctx = PinescriptParser.Additive_expressionContext(self, _parentctx, _parentState)
                    self.pushNewRecursionContext(localctx, _startState, self.RULE_additive_expression)
                    self.state = 619
                    if not self.precpred(self._ctx, 2):
                        from antlr4.error.Errors import FailedPredicateException
                        raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                    self.state = 620
                    self.additive_op()
                    self.state = 621
                    self.multiplicative_expression(0) 
                self.state = 627
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,50,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class Additive_opContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def PLUS(self):
            return self.getToken(PinescriptParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(PinescriptParser.MINUS, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_additive_op

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAdditive_op" ):
                return visitor.visitAdditive_op(self)
            else:
                return visitor.visitChildren(self)




    def additive_op(self):

        localctx = PinescriptParser.Additive_opContext(self, self._ctx, self.state)
        self.enterRule(localctx, 142, self.RULE_additive_op)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 628
            _la = self._input.LA(1)
            if not(_la==46 or _la==47):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Multiplicative_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Unary_expressionContext,0)


        def multiplicative_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Multiplicative_expressionContext,0)


        def multiplicative_op(self):
            return self.getTypedRuleContext(PinescriptParser.Multiplicative_opContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_multiplicative_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMultiplicative_expression" ):
                return visitor.visitMultiplicative_expression(self)
            else:
                return visitor.visitChildren(self)



    def multiplicative_expression(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = PinescriptParser.Multiplicative_expressionContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 144
        self.enterRecursionRule(localctx, 144, self.RULE_multiplicative_expression, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 631
            self.unary_expression()
            self._ctx.stop = self._input.LT(-1)
            self.state = 639
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,51,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    localctx = PinescriptParser.Multiplicative_expressionContext(self, _parentctx, _parentState)
                    self.pushNewRecursionContext(localctx, _startState, self.RULE_multiplicative_expression)
                    self.state = 633
                    if not self.precpred(self._ctx, 2):
                        from antlr4.error.Errors import FailedPredicateException
                        raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                    self.state = 634
                    self.multiplicative_op()
                    self.state = 635
                    self.unary_expression() 
                self.state = 641
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,51,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class Multiplicative_opContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STAR(self):
            return self.getToken(PinescriptParser.STAR, 0)

        def SLASH(self):
            return self.getToken(PinescriptParser.SLASH, 0)

        def PERCENT(self):
            return self.getToken(PinescriptParser.PERCENT, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_multiplicative_op

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMultiplicative_op" ):
                return visitor.visitMultiplicative_op(self)
            else:
                return visitor.visitChildren(self)




    def multiplicative_op(self):

        localctx = PinescriptParser.Multiplicative_opContext(self, self._ctx, self.state)
        self.enterRule(localctx, 146, self.RULE_multiplicative_op)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 642
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 1970324836974592) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Unary_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def unary_op(self):
            return self.getTypedRuleContext(PinescriptParser.Unary_opContext,0)


        def unary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Unary_expressionContext,0)


        def primary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Primary_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_unary_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitUnary_expression" ):
                return visitor.visitUnary_expression(self)
            else:
                return visitor.visitChildren(self)




    def unary_expression(self):

        localctx = PinescriptParser.Unary_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 148, self.RULE_unary_expression)
        try:
            self.state = 648
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [19, 46, 47]:
                self.enterOuterAlt(localctx, 1)
                self.state = 644
                self.unary_op()
                self.state = 645
                self.unary_expression()
                pass
            elif token in [7, 10, 12, 17, 18, 21, 22, 25, 26, 30, 32, 57, 58, 59, 60]:
                self.enterOuterAlt(localctx, 2)
                self.state = 647
                self.primary_expression(0)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Unary_opContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NOT(self):
            return self.getToken(PinescriptParser.NOT, 0)

        def PLUS(self):
            return self.getToken(PinescriptParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(PinescriptParser.MINUS, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_unary_op

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitUnary_op" ):
                return visitor.visitUnary_op(self)
            else:
                return visitor.visitChildren(self)




    def unary_op(self):

        localctx = PinescriptParser.Unary_opContext(self, self._ctx, self.state)
        self.enterRule(localctx, 150, self.RULE_unary_op)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 650
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 211106233057280) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Primary_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser


        def getRuleIndex(self):
            return PinescriptParser.RULE_primary_expression

     
        def copyFrom(self, ctx:ParserRuleContext):
            super().copyFrom(ctx)


    class Primary_expression_attributeContext(Primary_expressionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a PinescriptParser.Primary_expressionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def primary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Primary_expressionContext,0)

        def DOT(self):
            return self.getToken(PinescriptParser.DOT, 0)
        def name_load(self):
            return self.getTypedRuleContext(PinescriptParser.Name_loadContext,0)


        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimary_expression_attribute" ):
                return visitor.visitPrimary_expression_attribute(self)
            else:
                return visitor.visitChildren(self)


    class Primary_expression_callContext(Primary_expressionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a PinescriptParser.Primary_expressionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def primary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Primary_expressionContext,0)

        def LPAR(self):
            return self.getToken(PinescriptParser.LPAR, 0)
        def RPAR(self):
            return self.getToken(PinescriptParser.RPAR, 0)
        def template_spec_suffix(self):
            return self.getTypedRuleContext(PinescriptParser.Template_spec_suffixContext,0)

        def argument_list(self):
            return self.getTypedRuleContext(PinescriptParser.Argument_listContext,0)


        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimary_expression_call" ):
                return visitor.visitPrimary_expression_call(self)
            else:
                return visitor.visitChildren(self)


    class Primary_expression_fallbackContext(Primary_expressionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a PinescriptParser.Primary_expressionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def atomic_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Atomic_expressionContext,0)


        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimary_expression_fallback" ):
                return visitor.visitPrimary_expression_fallback(self)
            else:
                return visitor.visitChildren(self)


    class Primary_expression_subscriptContext(Primary_expressionContext):

        def __init__(self, parser, ctx:ParserRuleContext): # actually a PinescriptParser.Primary_expressionContext
            super().__init__(parser)
            self.copyFrom(ctx)

        def primary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Primary_expressionContext,0)

        def LSQB(self):
            return self.getToken(PinescriptParser.LSQB, 0)
        def subscript_slice(self):
            return self.getTypedRuleContext(PinescriptParser.Subscript_sliceContext,0)

        def RSQB(self):
            return self.getToken(PinescriptParser.RSQB, 0)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimary_expression_subscript" ):
                return visitor.visitPrimary_expression_subscript(self)
            else:
                return visitor.visitChildren(self)



    def primary_expression(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = PinescriptParser.Primary_expressionContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 152
        self.enterRecursionRule(localctx, 152, self.RULE_primary_expression, _p)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            localctx = PinescriptParser.Primary_expression_fallbackContext(self, localctx)
            self._ctx = localctx
            _prevctx = localctx

            self.state = 653
            self.atomic_expression()
            self._ctx.stop = self._input.LT(-1)
            self.state = 674
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,56,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 672
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,55,self._ctx)
                    if la_ == 1:
                        localctx = PinescriptParser.Primary_expression_attributeContext(self, PinescriptParser.Primary_expressionContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_primary_expression)
                        self.state = 655
                        if not self.precpred(self._ctx, 4):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 4)")
                        self.state = 656
                        self.match(PinescriptParser.DOT)
                        self.state = 657
                        self.name_load()
                        pass

                    elif la_ == 2:
                        localctx = PinescriptParser.Primary_expression_callContext(self, PinescriptParser.Primary_expressionContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_primary_expression)
                        self.state = 658
                        if not self.precpred(self._ctx, 3):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 3)")
                        self.state = 660
                        self._errHandler.sync(self)
                        _la = self._input.LA(1)
                        if _la==34:
                            self.state = 659
                            self.template_spec_suffix()


                        self.state = 662
                        self.match(PinescriptParser.LPAR)
                        self.state = 664
                        self._errHandler.sync(self)
                        _la = self._input.LA(1)
                        if (((_la) & ~0x3f) == 0 and ((1 << _la) & 2161938932846957696) != 0):
                            self.state = 663
                            self.argument_list()


                        self.state = 666
                        self.match(PinescriptParser.RPAR)
                        pass

                    elif la_ == 3:
                        localctx = PinescriptParser.Primary_expression_subscriptContext(self, PinescriptParser.Primary_expressionContext(self, _parentctx, _parentState))
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_primary_expression)
                        self.state = 667
                        if not self.precpred(self._ctx, 2):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                        self.state = 668
                        self.match(PinescriptParser.LSQB)
                        self.state = 669
                        self.subscript_slice()
                        self.state = 670
                        self.match(PinescriptParser.RSQB)
                        pass

             
                self.state = 676
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,56,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class Argument_listContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def argument_definition(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Argument_definitionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Argument_definitionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_argument_list

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgument_list" ):
                return visitor.visitArgument_list(self)
            else:
                return visitor.visitChildren(self)




    def argument_list(self):

        localctx = PinescriptParser.Argument_listContext(self, self._ctx, self.state)
        self.enterRule(localctx, 154, self.RULE_argument_list)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 677
            self.argument_definition()
            self.state = 682
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,57,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 678
                    self.match(PinescriptParser.COMMA)
                    self.state = 679
                    self.argument_definition() 
                self.state = 684
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,57,self._ctx)

            self.state = 686
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 685
                self.match(PinescriptParser.COMMA)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Argument_definitionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def EQUAL(self):
            return self.getToken(PinescriptParser.EQUAL, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_argument_definition

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgument_definition" ):
                return visitor.visitArgument_definition(self)
            else:
                return visitor.visitChildren(self)




    def argument_definition(self):

        localctx = PinescriptParser.Argument_definitionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 156, self.RULE_argument_definition)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 691
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,59,self._ctx)
            if la_ == 1:
                self.state = 688
                self.name_store()
                self.state = 689
                self.match(PinescriptParser.EQUAL)


            self.state = 693
            self.expression()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Subscript_sliceContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.ExpressionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_subscript_slice

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSubscript_slice" ):
                return visitor.visitSubscript_slice(self)
            else:
                return visitor.visitChildren(self)




    def subscript_slice(self):

        localctx = PinescriptParser.Subscript_sliceContext(self, self._ctx, self.state)
        self.enterRule(localctx, 158, self.RULE_subscript_slice)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 695
            self.expression()
            self.state = 700
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,60,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 696
                    self.match(PinescriptParser.COMMA)
                    self.state = 697
                    self.expression() 
                self.state = 702
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,60,self._ctx)

            self.state = 704
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 703
                self.match(PinescriptParser.COMMA)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Atomic_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_load(self):
            return self.getTypedRuleContext(PinescriptParser.Name_loadContext,0)


        def literal_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Literal_expressionContext,0)


        def grouped_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Grouped_expressionContext,0)


        def tuple_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Tuple_expressionContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_atomic_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAtomic_expression" ):
                return visitor.visitAtomic_expression(self)
            else:
                return visitor.visitChildren(self)




    def atomic_expression(self):

        localctx = PinescriptParser.Atomic_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 160, self.RULE_atomic_expression)
        try:
            self.state = 710
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [7, 10, 17, 18, 21, 22, 25, 57]:
                self.enterOuterAlt(localctx, 1)
                self.state = 706
                self.name_load()
                pass
            elif token in [12, 26, 58, 59, 60]:
                self.enterOuterAlt(localctx, 2)
                self.state = 707
                self.literal_expression()
                pass
            elif token in [30]:
                self.enterOuterAlt(localctx, 3)
                self.state = 708
                self.grouped_expression()
                pass
            elif token in [32]:
                self.enterOuterAlt(localctx, 4)
                self.state = 709
                self.tuple_expression()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Literal_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def literal_number(self):
            return self.getTypedRuleContext(PinescriptParser.Literal_numberContext,0)


        def literal_string(self):
            return self.getTypedRuleContext(PinescriptParser.Literal_stringContext,0)


        def literal_bool(self):
            return self.getTypedRuleContext(PinescriptParser.Literal_boolContext,0)


        def literal_color(self):
            return self.getTypedRuleContext(PinescriptParser.Literal_colorContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_literal_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral_expression" ):
                return visitor.visitLiteral_expression(self)
            else:
                return visitor.visitChildren(self)




    def literal_expression(self):

        localctx = PinescriptParser.Literal_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 162, self.RULE_literal_expression)
        try:
            self.state = 716
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [58]:
                self.enterOuterAlt(localctx, 1)
                self.state = 712
                self.literal_number()
                pass
            elif token in [59]:
                self.enterOuterAlt(localctx, 2)
                self.state = 713
                self.literal_string()
                pass
            elif token in [12, 26]:
                self.enterOuterAlt(localctx, 3)
                self.state = 714
                self.literal_bool()
                pass
            elif token in [60]:
                self.enterOuterAlt(localctx, 4)
                self.state = 715
                self.literal_color()
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Literal_numberContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NUMBER(self):
            return self.getToken(PinescriptParser.NUMBER, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_literal_number

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral_number" ):
                return visitor.visitLiteral_number(self)
            else:
                return visitor.visitChildren(self)




    def literal_number(self):

        localctx = PinescriptParser.Literal_numberContext(self, self._ctx, self.state)
        self.enterRule(localctx, 164, self.RULE_literal_number)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 718
            self.match(PinescriptParser.NUMBER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Literal_stringContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(PinescriptParser.STRING, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_literal_string

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral_string" ):
                return visitor.visitLiteral_string(self)
            else:
                return visitor.visitChildren(self)




    def literal_string(self):

        localctx = PinescriptParser.Literal_stringContext(self, self._ctx, self.state)
        self.enterRule(localctx, 166, self.RULE_literal_string)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 720
            self.match(PinescriptParser.STRING)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Literal_boolContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def TRUE(self):
            return self.getToken(PinescriptParser.TRUE, 0)

        def FALSE(self):
            return self.getToken(PinescriptParser.FALSE, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_literal_bool

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral_bool" ):
                return visitor.visitLiteral_bool(self)
            else:
                return visitor.visitChildren(self)




    def literal_bool(self):

        localctx = PinescriptParser.Literal_boolContext(self, self._ctx, self.state)
        self.enterRule(localctx, 168, self.RULE_literal_bool)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 722
            _la = self._input.LA(1)
            if not(_la==12 or _la==26):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Literal_colorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def COLOR(self):
            return self.getToken(PinescriptParser.COLOR, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_literal_color

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral_color" ):
                return visitor.visitLiteral_color(self)
            else:
                return visitor.visitChildren(self)




    def literal_color(self):

        localctx = PinescriptParser.Literal_colorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 170, self.RULE_literal_color)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 724
            self.match(PinescriptParser.COLOR)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Grouped_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAR(self):
            return self.getToken(PinescriptParser.LPAR, 0)

        def expression(self):
            return self.getTypedRuleContext(PinescriptParser.ExpressionContext,0)


        def RPAR(self):
            return self.getToken(PinescriptParser.RPAR, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_grouped_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitGrouped_expression" ):
                return visitor.visitGrouped_expression(self)
            else:
                return visitor.visitChildren(self)




    def grouped_expression(self):

        localctx = PinescriptParser.Grouped_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 172, self.RULE_grouped_expression)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 726
            self.match(PinescriptParser.LPAR)
            self.state = 727
            self.expression()
            self.state = 728
            self.match(PinescriptParser.RPAR)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Tuple_expressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LSQB(self):
            return self.getToken(PinescriptParser.LSQB, 0)

        def RSQB(self):
            return self.getToken(PinescriptParser.RSQB, 0)

        def expression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.ExpressionContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.ExpressionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_tuple_expression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTuple_expression" ):
                return visitor.visitTuple_expression(self)
            else:
                return visitor.visitChildren(self)




    def tuple_expression(self):

        localctx = PinescriptParser.Tuple_expressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 174, self.RULE_tuple_expression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 730
            self.match(PinescriptParser.LSQB)
            self.state = 742
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 2161938932846957696) != 0):
                self.state = 731
                self.expression()
                self.state = 736
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,64,self._ctx)
                while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                    if _alt==1:
                        self.state = 732
                        self.match(PinescriptParser.COMMA)
                        self.state = 733
                        self.expression() 
                    self.state = 738
                    self._errHandler.sync(self)
                    _alt = self._interp.adaptivePredict(self._input,64,self._ctx)

                self.state = 740
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==43:
                    self.state = 739
                    self.match(PinescriptParser.COMMA)




            self.state = 744
            self.match(PinescriptParser.RSQB)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Import_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IMPORT(self):
            return self.getToken(PinescriptParser.IMPORT, 0)

        def name(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.NameContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.NameContext,i)


        def SLASH(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.SLASH)
            else:
                return self.getToken(PinescriptParser.SLASH, i)

        def literal_number(self):
            return self.getTypedRuleContext(PinescriptParser.Literal_numberContext,0)


        def AS(self):
            return self.getToken(PinescriptParser.AS, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_import_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitImport_statement" ):
                return visitor.visitImport_statement(self)
            else:
                return visitor.visitChildren(self)




    def import_statement(self):

        localctx = PinescriptParser.Import_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 176, self.RULE_import_statement)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 746
            self.match(PinescriptParser.IMPORT)
            self.state = 747
            self.name()
            self.state = 748
            self.match(PinescriptParser.SLASH)
            self.state = 749
            self.name()
            self.state = 750
            self.match(PinescriptParser.SLASH)
            self.state = 751
            self.literal_number()
            self.state = 754
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==4:
                self.state = 752
                self.match(PinescriptParser.AS)
                self.state = 753
                self.name()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Break_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def BREAK(self):
            return self.getToken(PinescriptParser.BREAK, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_break_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBreak_statement" ):
                return visitor.visitBreak_statement(self)
            else:
                return visitor.visitChildren(self)




    def break_statement(self):

        localctx = PinescriptParser.Break_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 178, self.RULE_break_statement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 756
            self.match(PinescriptParser.BREAK)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Continue_statementContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CONTINUE(self):
            return self.getToken(PinescriptParser.CONTINUE, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_continue_statement

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitContinue_statement" ):
                return visitor.visitContinue_statement(self)
            else:
                return visitor.visitChildren(self)




    def continue_statement(self):

        localctx = PinescriptParser.Continue_statementContext(self, self._ctx, self.state)
        self.enterRule(localctx, 180, self.RULE_continue_statement)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 758
            self.match(PinescriptParser.CONTINUE)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Variable_declarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def declaration_mode(self):
            return self.getTypedRuleContext(PinescriptParser.Declaration_modeContext,0)


        def type_specification(self):
            return self.getTypedRuleContext(PinescriptParser.Type_specificationContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_variable_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitVariable_declaration" ):
                return visitor.visitVariable_declaration(self)
            else:
                return visitor.visitChildren(self)




    def variable_declaration(self):

        localctx = PinescriptParser.Variable_declarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 182, self.RULE_variable_declaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 761
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==27 or _la==28:
                self.state = 760
                self.declaration_mode()


            self.state = 764
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,69,self._ctx)
            if la_ == 1:
                self.state = 763
                self.type_specification()


            self.state = 766
            self.name_store()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Tuple_declarationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LSQB(self):
            return self.getToken(PinescriptParser.LSQB, 0)

        def name_store(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Name_storeContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Name_storeContext,i)


        def RSQB(self):
            return self.getToken(PinescriptParser.RSQB, 0)

        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_tuple_declaration

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTuple_declaration" ):
                return visitor.visitTuple_declaration(self)
            else:
                return visitor.visitChildren(self)




    def tuple_declaration(self):

        localctx = PinescriptParser.Tuple_declarationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 184, self.RULE_tuple_declaration)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 768
            self.match(PinescriptParser.LSQB)
            self.state = 769
            self.name_store()
            self.state = 774
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,70,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 770
                    self.match(PinescriptParser.COMMA)
                    self.state = 771
                    self.name_store() 
                self.state = 776
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,70,self._ctx)

            self.state = 778
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 777
                self.match(PinescriptParser.COMMA)


            self.state = 780
            self.match(PinescriptParser.RSQB)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Declaration_modeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def VARIP(self):
            return self.getToken(PinescriptParser.VARIP, 0)

        def VAR(self):
            return self.getToken(PinescriptParser.VAR, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_declaration_mode

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitDeclaration_mode" ):
                return visitor.visitDeclaration_mode(self)
            else:
                return visitor.visitChildren(self)




    def declaration_mode(self):

        localctx = PinescriptParser.Declaration_modeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 186, self.RULE_declaration_mode)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 782
            _la = self._input.LA(1)
            if not(_la==27 or _la==28):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Assignment_targetContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def assignment_target_attribute(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_target_attributeContext,0)


        def assignment_target_subscript(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_target_subscriptContext,0)


        def assignment_target_name(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_target_nameContext,0)


        def assignment_target_group(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_target_groupContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_assignment_target

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignment_target" ):
                return visitor.visitAssignment_target(self)
            else:
                return visitor.visitChildren(self)




    def assignment_target(self):

        localctx = PinescriptParser.Assignment_targetContext(self, self._ctx, self.state)
        self.enterRule(localctx, 188, self.RULE_assignment_target)
        try:
            self.state = 788
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,72,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 784
                self.assignment_target_attribute()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 785
                self.assignment_target_subscript()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 786
                self.assignment_target_name()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 787
                self.assignment_target_group()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Assignment_target_attributeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Primary_expressionContext,0)


        def DOT(self):
            return self.getToken(PinescriptParser.DOT, 0)

        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_assignment_target_attribute

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignment_target_attribute" ):
                return visitor.visitAssignment_target_attribute(self)
            else:
                return visitor.visitChildren(self)




    def assignment_target_attribute(self):

        localctx = PinescriptParser.Assignment_target_attributeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 190, self.RULE_assignment_target_attribute)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 790
            self.primary_expression(0)
            self.state = 791
            self.match(PinescriptParser.DOT)
            self.state = 792
            self.name_store()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Assignment_target_subscriptContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primary_expression(self):
            return self.getTypedRuleContext(PinescriptParser.Primary_expressionContext,0)


        def LSQB(self):
            return self.getToken(PinescriptParser.LSQB, 0)

        def subscript_slice(self):
            return self.getTypedRuleContext(PinescriptParser.Subscript_sliceContext,0)


        def RSQB(self):
            return self.getToken(PinescriptParser.RSQB, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_assignment_target_subscript

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignment_target_subscript" ):
                return visitor.visitAssignment_target_subscript(self)
            else:
                return visitor.visitChildren(self)




    def assignment_target_subscript(self):

        localctx = PinescriptParser.Assignment_target_subscriptContext(self, self._ctx, self.state)
        self.enterRule(localctx, 192, self.RULE_assignment_target_subscript)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 794
            self.primary_expression(0)
            self.state = 795
            self.match(PinescriptParser.LSQB)
            self.state = 796
            self.subscript_slice()
            self.state = 797
            self.match(PinescriptParser.RSQB)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Assignment_target_nameContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_store(self):
            return self.getTypedRuleContext(PinescriptParser.Name_storeContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_assignment_target_name

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignment_target_name" ):
                return visitor.visitAssignment_target_name(self)
            else:
                return visitor.visitChildren(self)




    def assignment_target_name(self):

        localctx = PinescriptParser.Assignment_target_nameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 194, self.RULE_assignment_target_name)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 799
            self.name_store()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Assignment_target_groupContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAR(self):
            return self.getToken(PinescriptParser.LPAR, 0)

        def assignment_target(self):
            return self.getTypedRuleContext(PinescriptParser.Assignment_targetContext,0)


        def RPAR(self):
            return self.getToken(PinescriptParser.RPAR, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_assignment_target_group

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAssignment_target_group" ):
                return visitor.visitAssignment_target_group(self)
            else:
                return visitor.visitChildren(self)




    def assignment_target_group(self):

        localctx = PinescriptParser.Assignment_target_groupContext(self, self._ctx, self.state)
        self.enterRule(localctx, 196, self.RULE_assignment_target_group)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 801
            self.match(PinescriptParser.LPAR)
            self.state = 802
            self.assignment_target()
            self.state = 803
            self.match(PinescriptParser.RPAR)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Augassign_opContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STAREQUAL(self):
            return self.getToken(PinescriptParser.STAREQUAL, 0)

        def SLASHEQUAL(self):
            return self.getToken(PinescriptParser.SLASHEQUAL, 0)

        def PERCENTEQUAL(self):
            return self.getToken(PinescriptParser.PERCENTEQUAL, 0)

        def PLUSEQUAL(self):
            return self.getToken(PinescriptParser.PLUSEQUAL, 0)

        def MINEQUAL(self):
            return self.getToken(PinescriptParser.MINEQUAL, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_augassign_op

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAugassign_op" ):
                return visitor.visitAugassign_op(self)
            else:
                return visitor.visitChildren(self)




    def augassign_op(self):

        localctx = PinescriptParser.Augassign_opContext(self, self._ctx, self.state)
        self.enterRule(localctx, 198, self.RULE_augassign_op)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 805
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 69805794224242688) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Type_specificationContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def attributed_type_name(self):
            return self.getTypedRuleContext(PinescriptParser.Attributed_type_nameContext,0)


        def type_qualifier(self):
            return self.getTypedRuleContext(PinescriptParser.Type_qualifierContext,0)


        def template_spec_suffix(self):
            return self.getTypedRuleContext(PinescriptParser.Template_spec_suffixContext,0)


        def array_type_suffix(self):
            return self.getTypedRuleContext(PinescriptParser.Array_type_suffixContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_type_specification

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitType_specification" ):
                return visitor.visitType_specification(self)
            else:
                return visitor.visitChildren(self)




    def type_specification(self):

        localctx = PinescriptParser.Type_specificationContext(self, self._ctx, self.state)
        self.enterRule(localctx, 200, self.RULE_type_specification)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 808
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,73,self._ctx)
            if la_ == 1:
                self.state = 807
                self.type_qualifier()


            self.state = 810
            self.attributed_type_name()
            self.state = 812
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==34:
                self.state = 811
                self.template_spec_suffix()


            self.state = 815
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==32:
                self.state = 814
                self.array_type_suffix()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Type_qualifierContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def CONST(self):
            return self.getToken(PinescriptParser.CONST, 0)

        def INPUT(self):
            return self.getToken(PinescriptParser.INPUT, 0)

        def SIMPLE(self):
            return self.getToken(PinescriptParser.SIMPLE, 0)

        def SERIES(self):
            return self.getToken(PinescriptParser.SERIES, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_type_qualifier

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitType_qualifier" ):
                return visitor.visitType_qualifier(self)
            else:
                return visitor.visitChildren(self)




    def type_qualifier(self):

        localctx = PinescriptParser.Type_qualifierContext(self, self._ctx, self.state)
        self.enterRule(localctx, 202, self.RULE_type_qualifier)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 817
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 6422656) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Attributed_type_nameContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name_load(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Name_loadContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Name_loadContext,i)


        def DOT(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.DOT)
            else:
                return self.getToken(PinescriptParser.DOT, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_attributed_type_name

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAttributed_type_name" ):
                return visitor.visitAttributed_type_name(self)
            else:
                return visitor.visitChildren(self)




    def attributed_type_name(self):

        localctx = PinescriptParser.Attributed_type_nameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 204, self.RULE_attributed_type_name)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 819
            self.name_load()
            self.state = 824
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==42:
                self.state = 820
                self.match(PinescriptParser.DOT)
                self.state = 821
                self.name_load()
                self.state = 826
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Template_spec_suffixContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LESS(self):
            return self.getToken(PinescriptParser.LESS, 0)

        def GREATER(self):
            return self.getToken(PinescriptParser.GREATER, 0)

        def type_argument_list(self):
            return self.getTypedRuleContext(PinescriptParser.Type_argument_listContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_template_spec_suffix

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitTemplate_spec_suffix" ):
                return visitor.visitTemplate_spec_suffix(self)
            else:
                return visitor.visitChildren(self)




    def template_spec_suffix(self):

        localctx = PinescriptParser.Template_spec_suffixContext(self, self._ctx, self.state)
        self.enterRule(localctx, 206, self.RULE_template_spec_suffix)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 827
            self.match(PinescriptParser.LESS)
            self.state = 829
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 144115188116096128) != 0):
                self.state = 828
                self.type_argument_list()


            self.state = 831
            self.match(PinescriptParser.GREATER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Array_type_suffixContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LSQB(self):
            return self.getToken(PinescriptParser.LSQB, 0)

        def RSQB(self):
            return self.getToken(PinescriptParser.RSQB, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_array_type_suffix

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArray_type_suffix" ):
                return visitor.visitArray_type_suffix(self)
            else:
                return visitor.visitChildren(self)




    def array_type_suffix(self):

        localctx = PinescriptParser.Array_type_suffixContext(self, self._ctx, self.state)
        self.enterRule(localctx, 208, self.RULE_array_type_suffix)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 833
            self.match(PinescriptParser.LSQB)
            self.state = 834
            self.match(PinescriptParser.RSQB)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Type_argument_listContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def type_specification(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.Type_specificationContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.Type_specificationContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(PinescriptParser.COMMA)
            else:
                return self.getToken(PinescriptParser.COMMA, i)

        def getRuleIndex(self):
            return PinescriptParser.RULE_type_argument_list

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitType_argument_list" ):
                return visitor.visitType_argument_list(self)
            else:
                return visitor.visitChildren(self)




    def type_argument_list(self):

        localctx = PinescriptParser.Type_argument_listContext(self, self._ctx, self.state)
        self.enterRule(localctx, 210, self.RULE_type_argument_list)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 836
            self.type_specification()
            self.state = 841
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,78,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 837
                    self.match(PinescriptParser.COMMA)
                    self.state = 838
                    self.type_specification() 
                self.state = 843
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,78,self._ctx)

            self.state = 845
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==43:
                self.state = 844
                self.match(PinescriptParser.COMMA)


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NameContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NAME(self):
            return self.getToken(PinescriptParser.NAME, 0)

        def TYPE(self):
            return self.getToken(PinescriptParser.TYPE, 0)

        def METHOD(self):
            return self.getToken(PinescriptParser.METHOD, 0)

        def CONST(self):
            return self.getToken(PinescriptParser.CONST, 0)

        def INPUT(self):
            return self.getToken(PinescriptParser.INPUT, 0)

        def SIMPLE(self):
            return self.getToken(PinescriptParser.SIMPLE, 0)

        def SERIES(self):
            return self.getToken(PinescriptParser.SERIES, 0)

        def ENUM(self):
            return self.getToken(PinescriptParser.ENUM, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_name

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitName" ):
                return visitor.visitName(self)
            else:
                return visitor.visitChildren(self)




    def name(self):

        localctx = PinescriptParser.NameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 212, self.RULE_name)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 847
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 144115188116096128) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Name_loadContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name(self):
            return self.getTypedRuleContext(PinescriptParser.NameContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_name_load

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitName_load" ):
                return visitor.visitName_load(self)
            else:
                return visitor.visitChildren(self)




    def name_load(self):

        localctx = PinescriptParser.Name_loadContext(self, self._ctx, self.state)
        self.enterRule(localctx, 214, self.RULE_name_load)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 849
            self.name()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Name_storeContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name(self):
            return self.getTypedRuleContext(PinescriptParser.NameContext,0)


        def getRuleIndex(self):
            return PinescriptParser.RULE_name_store

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitName_store" ):
                return visitor.visitName_store(self)
            else:
                return visitor.visitChildren(self)




    def name_store(self):

        localctx = PinescriptParser.Name_storeContext(self, self._ctx, self.state)
        self.enterRule(localctx, 216, self.RULE_name_store)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 851
            self.name()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CommentsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def comment(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(PinescriptParser.CommentContext)
            else:
                return self.getTypedRuleContext(PinescriptParser.CommentContext,i)


        def getRuleIndex(self):
            return PinescriptParser.RULE_comments

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitComments" ):
                return visitor.visitComments(self)
            else:
                return visitor.visitChildren(self)




    def comments(self):

        localctx = PinescriptParser.CommentsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 218, self.RULE_comments)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 854 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 853
                self.comment()
                self.state = 856 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==63):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CommentContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def COMMENT(self):
            return self.getToken(PinescriptParser.COMMENT, 0)

        def getRuleIndex(self):
            return PinescriptParser.RULE_comment

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitComment" ):
                return visitor.visitComment(self)
            else:
                return visitor.visitChildren(self)




    def comment(self):

        localctx = PinescriptParser.CommentContext(self, self._ctx, self.state)
        self.enterRule(localctx, 220, self.RULE_comment)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 858
            self.match(PinescriptParser.COMMENT)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[70] = self.additive_expression_sempred
        self._predicates[72] = self.multiplicative_expression_sempred
        self._predicates[76] = self.primary_expression_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def additive_expression_sempred(self, localctx:Additive_expressionContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 2)
         

    def multiplicative_expression_sempred(self, localctx:Multiplicative_expressionContext, predIndex:int):
            if predIndex == 1:
                return self.precpred(self._ctx, 2)
         

    def primary_expression_sempred(self, localctx:Primary_expressionContext, predIndex:int):
            if predIndex == 2:
                return self.precpred(self._ctx, 4)
         

            if predIndex == 3:
                return self.precpred(self._ctx, 3)
         

            if predIndex == 4:
                return self.precpred(self._ctx, 2)
         




