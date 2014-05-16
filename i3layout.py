#!/usr/bin/env python2.7

import sys
import getopt
import time
import logging
import ConfigParser
from os import getenv
from os.path import exists

import numpy as np
import i3

FORMAT = "%(module)s.%(funcName)s %(levelname)s: %(message)s"
UNIT = 100

def layout2arr(layout):
    logging.debug("input: %s", layout)
    a = layout.split('\n')
    b = []
    for line in a:
        if len(line) > 0:
            b.append(line)
    d = []
    for line in b:
        for n in line:
            d.append(int(n))
    res = np.array(d).reshape(len(b),len(b[0]))
    logging.debug("output: %s", res)
    return res

def load_config(path):
    tasks = []
    idx = 0
    with open(path, 'r') as f:
        layout = ""
        progs = []
        for line in f:
            line = line.replace('\n','')
            logging.debug("current line: %s", line)
            line = line.strip()
            if line.startswith("//"):
                continue
            elif line.startswith('#'):
                line = line.replace('#','')
                line = line.strip()
                layout_mode = True
                if ":" in line:
                    name, ws = line.split(":")
                else:
                    idx += 1
                    name = line
                    ws = str(idx)
            elif line.startswith('-'):
                layout_mode = False
            elif len(line) == 0:
                logging.debug("add layout")
                tasks.append({'name': name, 'workspace': ws,
                'layout': layout, 'progs': progs})
                layout = ""
                progs = []
            else:
                if layout_mode:
                    layout += line + "\n"
                else:
                    progs.append(line)
    tasks.append({'name': name, 'workspace': ws,
    'layout': layout, 'progs': progs})
    return tasks


def vertical(mat, idx):
    if idx < mat.shape[0]:
        logging.info("split at %d", idx)
        return (np.vsplit(mat, [idx]), mat[idx, 0])
    else:
        logging.info("split overrun")
        return False, None


def horizontal(mat, idx):
    if idx < mat.shape[1]:
        logging.info("split at %d", idx)
        return (np.hsplit(mat, [idx]), mat[0,idx])
    else:
        logging.info("split overrun")
        return False, None


def split_check(x,y):
    logging.debug("\n%s\n---\n%s", x, y)
    for idx in np.unique(x):
        if idx in np.unique(y):
            logging.info("split failed")
            return False
    logging.info("split worked")
    return True


def step(arr, func, nfunc, flagged=False):
    logging.debug("fields: %s", np.unique(arr))
    if np.unique(arr).shape[0] == 1:
        logging.info("found leaf")
        return True, None
    else:
        idx = 1
        c = func(arr, idx)
        s = c[0]
        while(s != False):
            if split_check(s[0],s[1]):
                l, lop = step(s[0], nfunc, func)
                r, rop= step(s[1], nfunc, func)
                if l and r:
                    op = [(func.__name__, c[1], idx),lop, rop]
                    return True, op
            idx += 1
            c = func(arr, idx)
            s = c[0]
        if flagged:
            return False, None
        return step(arr, nfunc, func, True)


def i3conv(arr, dim_x, dim_y, progs):
    logging.debug("current field size %d : %d", dim_x, dim_y)
    if arr is None:
        return []
    op = arr[0][0]
    prog = arr[0][1]
    idx = arr[0][2]
    ops = [("split", op), ("exec", progs[prog-1])]
    if op == "horizontal":
        if idx != dim_x / 2.0:
            dx = dim_x / 2.0 - idx
            if dx < 0:
                com = "shrink"
            else: 
                com = "grow"
            ops.append(("resize", "%s left %d px or %d ppt" % (com, (abs(dx) * UNIT), abs(dx/float(dim_x)) * 100 ))) 
        new_dim_x_r = idx
        new_dim_x_l = dim_x - new_dim_x_r
    else:
        new_dim_x_l = new_dim_x_r = dim_x
    if op == "vertical":
        if idx != dim_y / 2.0:
            dy = dim_y / 2.0 - idx
            if dy < 0:
                com = "shrink"
            else:
                com = "grow"
            ops.append(("resize", "%s up %d px or %d ppt" % (com, (abs(dy) * UNIT), (abs(dy/float(dim_y))) * 100))) 
        new_dim_y_r = idx
        new_dim_y_l = dim_y - new_dim_y_r
    else:
        new_dim_y_l = new_dim_y_r = dim_y

    lops = i3conv(arr[2], new_dim_x_l, new_dim_y_l, progs)
    rops = i3conv(arr[1], new_dim_x_r, new_dim_y_r, progs)
    if lops is not 'x':
        ops.extend(lops)
    if rops is not 'x':
        if op == "vertical":
            back_op = ("focus", "up")
        else:
            back_op = ("focus", "left")
        ops.append(back_op)
        ops.extend(rops)
    return ops

#i3.command('workspace','4')
#i3.command('layout','default')
#i3.command('exec','gnome-terminal')
#i3.command('exec','gnome-terminal')


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg

def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hxvdi",
                ["help"])
            ws = layout = progs = None
            simulate = load = True
            verbose = debug = interactive = store = False
            for o, a in opts:
                if o in ('h', "help"):
                    raise Usage(None)
                elif o == '-x':
                    simulate = False
                elif o == '-v':
                    verbose = True
                elif o == '-d':
                    debug = True
                elif o == '-i':
                    interactive = True
                    load = False

        except getopt.error, msg:
             raise Usage(msg)
        # more code, unchanged
    except Usage, err:
        print >>sys.stderr, err.msg
        print >>sys.stderr, "for help use --help"
        return 2

    lvl = 'CRITICAL'
    if debug:
        lvl = 'DEBUG'
    elif verbose:
        lvl = 'INFO'
    logging.basicConfig(format=FORMAT, level=lvl, stream=sys.stdout)
    if interactive:
        ws = raw_input('set workspace: ')
        print "enter layout"
        layout = ""
        line = raw_input(">")
        while(line != ''):
            layout += "%s\n" % line
            line = raw_input(">")
        print "choose programs:"
        progs = []
        idx = 1
        line = raw_input("%d: " %idx)
        while(line != ''):
            progs.append(line)
            idx += 1
            line = raw_input("%d: " % idx)
        tasks = [{'name': None, 'workspace': ws,
                  'layout': layout, 'progs': progs}]   
    elif load:
        cfg_file = "%s/.i3/layouts"%getenv("HOME")
        if exists(cfg_file):
            tasks = load_config(cfg_file)
        else:
            print "ERROR: No layout file found. Please use the\
 interactive mode or use %s." % cfg_file
            f = open(cfg_file,"w")
            f.close()
            tasks = []

    for task in tasks:
        logging.info("current task: %s" % task)
        ws = task['workspace']
        layout = task['layout']
        progs = task['progs']
        x = layout2arr(layout)
        r = step(x, horizontal, vertical)
        logging.info("path: %s", r)
        if r[0]:
            #print r
            op = [("exec", progs[x[0,0]-1])]
            op.extend(i3conv(r[1],x.shape[1], x.shape[0], progs))

            logging.info("result: %s", op)

            if not simulate:
                i3.command("workspace", ws)
                time.sleep(0.1)

            for i in op:
                logging.debug("next op: %s", i)
                if not simulate:
                    i3.command(i[0],i[1])
                    if i[0] == "exec":
                        time.sleep(0.5)
                    else:
                        time.sleep(0.1)
        else:
            print "ERROR: No path found for layout!"
            print layout

if __name__ == "__main__":
    sys.exit(main())
