#!/usr/bin/python

"""
(C) Copyright 2016-2017 ALBA-CELLS
Authors: Marc Rosanes, Carlos Falcon, Zbigniew Reszela, Carlos Pascual
The program is distributed under the terms of the
GNU General Public License (or the Lesser GPL).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import datetime
import argparse
#import pprint
from operator import itemgetter
from tinydb import Query

from txm2nexuslib.xrmnex import xrmNXtomo, xrmReader
from txm2nexuslib.parser import get_db, get_file_paths

def get_samples(txm_txt_script):
    # Organize the files by samples

    #prettyprinter = pprint.PrettyPrinter(indent=4)
    root_path = os.path.dirname(os.path.abspath(txm_txt_script))

    db = get_db(txm_txt_script, use_existing_db=False)

    all_file_records = db.all()

    dates_samples_energies = []
    for record in all_file_records:
        dates_samples_energies.append(record["sample"] + "_" +
                                      str(record["date"]) + "_" +
                                      str(record["energy"]))
    dates_samples_energies = list(set(dates_samples_energies))

    samples = {}
    files_query = Query()

    for date_sample_energie in dates_samples_energies:

        files_by_zp = {}
        files_for_sample_subdict = {}

        energy = date_sample_energie.split('_')[-1]
        energy = float(energy)
        query_impl = (files_query.energy == energy)
        records_by_given_energy = db.search(query_impl)

        zps_for_given_energy = [record["zpz"] for record in
                                records_by_given_energy]
        zpz_positions_for_given_energy = sorted(set(zps_for_given_energy))

        for zpz in zpz_positions_for_given_energy:
            query_impl = ((files_query.energy == energy) &
                          (files_query.zpz == zpz) & (files_query.FF == False))
            fn_by_zpz_query = db.search(query_impl)
            sorted_fn_by_zpz_query = sorted(fn_by_zpz_query,
                                            key=itemgetter('angle'))

            files = get_file_paths(sorted_fn_by_zpz_query, root_path,
                                   use_subfolders=True,
                                   only_existing_files=False)
            files_by_zp[zpz] = files

        # Get FF image records
        fn_ff_query_by_energy = ((files_query.energy == energy) &
                                 (files_query.FF == True))
        query_output = db.search(fn_ff_query_by_energy)
        files_FF = get_file_paths(query_output, root_path,
                                  use_subfolders=True,
                                  only_existing_files=False)

        files_for_sample_subdict['tomos'] = files_by_zp
        files_for_sample_subdict['ff'] = files_FF
        samples[date_sample_energie] = files_for_sample_subdict

    #prettyprinter.pprint(samples)
    return samples


def main():

    print("\n")
    print(datetime.datetime.today())
    print("\n")

    description = 'Create a tomo hdf5 file per each group of existing xrm ' \
                  'files in the given directory'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('input_txm_script', metavar='input TXM txt file',
                        type=str, help='TXM txt script used as index for the '
                                       'xrm image files')
    parser.add_argument('--output-dir', type=str, default="./out/",
                        help='Directory where the hdf5 files will be created.')
    parser.add_argument('--title', type=str, default='X-ray tomography',
                        help="Sets the title of the tomography")
    parser.add_argument('--source-name', type=str, default='ALBA',
                        help="Sets the source name")
    parser.add_argument('--source-type', type=str,
                        default='Synchrotron X-ray Source',
                        help="Sets the source type")
    parser.add_argument('--source-probe', type=str, default='x-ray',
                        help="Sets the source probe. Possible options are:"
                             "'x-ray', 'neutron','electron'")
    parser.add_argument('--instrument-name', type=str, default='BL09 @ ALBA',
                        help="Sets the instrument name")

    args = parser.parse_args()

    txm_txt_script = args.input_txm_script
    output_dir = os.path.abspath(args.output_dir)
    print(output_dir)
    samples = get_samples(txm_txt_script)
    # Generate the hdf5 files
    for sample in samples.keys():
        tomos = samples[sample]['tomos']
        # Create FF reader
        ff_files = samples[sample]['ff']
        ffreader = xrmReader(ff_files)
        for tomo in tomos.keys():
            tomo_files = samples[sample]['tomos'][tomo]
            if len(ff_files) == 0:
                print "WARNING: %s of Sample: %s have not BrightField " \
                      "files." % (tomo, sample)
                continue
            reader = xrmReader(tomo_files)
            xrm = xrmNXtomo(reader, ffreader,
                            'sb',  # TODO: Not need?
                            'xrm2nexus',
                            hdf5_output_path=output_dir,
                            title=args.title,
                            zero_deg_in=None,  # TODO Not well implemented
                            zero_deg_final=None,  # TODO Not well implemented
                            sourcename=args.source_name,
                            sourcetype=args.source_type,
                            sourceprobe=args.source_probe,
                            instrument=args.instrument_name,
                            )
            xrm.convert_metadata()
            xrm.convert_tomography()

    print("\n")
    print(datetime.datetime.today())
    print("\n")


if __name__ == "__main__":
    main()
