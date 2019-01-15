import pickle
import argparse
from SSINS import util, INS, MF
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('-f', '--obsfile', help='Path to obsfile', required=True)
parser.add_argument('-s', '--shapes', help='The names of the shapes to integrate',
                    required=True, nargs='*')
parser.add_argument('--streak', action='store_false', help='Do not check for streaks')
parser.add_argument('-p', '--point', action='store_false', help='Do not check for points')
parser.add_argument('-d', '--shape_dict',
                    help='A pickled shape dictionary for match filtering')
parser.add_argument('--sig', default=5,
                    help='The significance threshold for match filtering')
parser.add_argument('-N', default=0, help='The N threshold')
parser.add_argument('-i', '--indir', help='The base directory of the INS',
                    required=True)
parser.add_argument('--flag_choice', help='The flag choice for the INS',
                    required=True)
parser.add_argument('-o', '--outdir', help='The output directory', required=True)
args = parser.parse_args()

if args.shape_dict is not None:
    with open(args.shape_dict, 'rb') as file:
        shape_dict = pickle.load(file)
else:
    shape_dict = {}

obslist = util.make_obslist(args.obsfile)

bright_dict = {args.sig: {shape: {} for shape in args.shapes}}
print(shape_dict)

for obs in obslist:
    read_paths = util.read_paths_construct(args.indir, args.flag_choice, obs, 'INS')
    ins = INS(obs=obs, outpath=args.outdir, read_paths=read_paths)
    mf = MF(ins, sig_thresh=args.sig, N_thresh=args.N, shape_dict=shape_dict,
            streak=args.streak, point=args.point)
    mf.apply_match_test(apply_N_thresh=True)
    for shape in args.shapes:
        events = [event[:-1] for event in ins.match_events if event[-1] == shape]
        sum = 0
        chan = shape[-1]
        if shape in ['TV6', 'TV7', 'TV8']:
            broad_events = [event[:-1] for event in ins.match_events if event[:-1] == 'broad%s' % chan]
            broad_events_times = [event[0] for event in broad_events]
            event_remove = []
            for event in events:
                if event[0] in broad_events_times:
                    event_remove.append(event)
            for event in event_remove:
                events.remove(event)
        for event in events:
            sum += np.sum(ins.data.data[event])
        bright_dict[args.sig][shape][obs] = sum
    del ins
    del mf

with open('%s/bright_dict.pik' % args.outdir, 'wb') as file:
    pickle.dump(bright_dict, file)