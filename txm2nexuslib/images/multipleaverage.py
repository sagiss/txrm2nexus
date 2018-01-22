#!/usr/bin/python

"""
(C) Copyright 2018 ALBA-CELLS
Author: Marc Rosanes Siscart
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
import time
from joblib import Parallel, delayed
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from txm2nexuslib.parser import get_file_paths
from txm2nexuslib.image.image_operate_lib import average_images
from txm2nexuslib.images.util import filter_file_index


def average_and_store(group_to_average_image_filenames,
                      dataset_for_averaging="data",
                      variable="zpz", description="",
                      dataset_store="data"):

    if variable == "zpz":
        zp_central = group_to_average_image_filenames[0]
        images_to_average_filenames = group_to_average_image_filenames[1]
        date_sample_energy_angle = group_to_average_image_filenames[2]
        fn_first = images_to_average_filenames[0]
        dir_name = os.path.dirname(fn_first)
        date = date_sample_energy_angle[0]
        sample = date_sample_energy_angle[1]
        energy = date_sample_energy_angle[2]
        angle = date_sample_energy_angle[3]
        output_fn = (str(date) + "_" + str(sample) + "_" + str(energy) +
                     "_" + str(angle) + "_" +
                     str(zp_central) + "_avg_zpz.hdf5")
        output_complete_fn = dir_name + "/" + output_fn
        average_images(images_to_average_filenames,
                       dataset_for_average=dataset_for_averaging,
                       description=description, store=True,
                       output_h5_fn=output_complete_fn,
                       dataset_store=dataset_store)

        record = {"filename": output_fn, "extension": ".hdf5",
                  "date": date, "sample": sample, "energy": energy,
                  "angle": angle, "average": True, "avg_by": "zpz",
                  "zpz": zp_central}
    return record


def average_images_for_many_img_groups(
        file_index_fn, table_name="hdf5_proc", dataset_for_averaging="data",
        variable="zpz", description="", dataset_store="data",
        date=None, sample=None, energy=None, cores=-2):
    """Average images of one experiment by zpz.
    If date, sample and/or energy are indicated, only the corresponding
    images for the given date, sample and/or energy are processed.
    The average of the different groups of images will be done in parallel:
    all cores but one used (Value=-2). All images of the same angle, for the
    different ZPz are averaged.
    """

    """
    TODO: In the future it should be made available, the
     average by variable == repetition.
     For the moment only the average by variable == zpz is implemented

     Finally this three features should exist:
     - average by same angle and different zpz positions
     - average by same angle, same zpz and different repetition
     - average by same angle, first by same zpz and different repetition,
     and afterwards by same angle and different zpz positions
    """

    start_time = time.time()
    root_path = os.path.dirname(os.path.abspath(file_index_fn))

    file_index_db = TinyDB(file_index_fn,
                           storage=CachingMiddleware(JSONStorage))
    db = file_index_db
    if table_name is not None:
        file_index_db = file_index_db.table(table_name)

    files_query = Query()
    file_index_db = filter_file_index(file_index_db, files_query,
                                      date=date, sample=sample,
                                      energy=energy, ff=False)

    all_file_records = file_index_db.all()
    n_files = len(all_file_records)

    dates_samples_energies_angles = []
    for record in all_file_records:
        dates_samples_energies_angles.append((record["date"],
                                              record["sample"],
                                              record["energy"],
                                              record["angle"]))
    dates_samples_energies_angles = list(set(dates_samples_energies_angles))

    averages_table = db.table("hdf5_averages")
    averages_table.purge()

    groups_to_average = []
    if variable == "zpz":
        for date_sample_energy_angle in dates_samples_energies_angles:
            date = date_sample_energy_angle[0]
            sample = date_sample_energy_angle[1]
            energy = date_sample_energy_angle[2]
            angle = date_sample_energy_angle[3]

            # Raw image records by given date, sample and energy
            query_cmd = ((files_query.date == date) &
                         (files_query.sample == sample) &
                         (files_query.energy == energy) &
                         (files_query.angle == angle))
            img_records = file_index_db.search(query_cmd)
            num_zpz = len(img_records)
            central_zpz = 0
            for img_record in img_records:
                central_zpz += img_record["zpz"]
            central_zpz /= round(float(num_zpz), 1)

            files = get_file_paths(img_records, root_path)
            central_zpz_with_group_to_average = [central_zpz]
            group_to_average = []
            for file in files:
                group_to_average.append(file)
            central_zpz_with_group_to_average.append(group_to_average)
            central_zpz_with_group_to_average.append(date_sample_energy_angle)
            groups_to_average.append(central_zpz_with_group_to_average)

    if groups_to_average[0][1]:
        records = Parallel(n_jobs=cores, backend="multiprocessing")(
            delayed(average_and_store)(
                group_to_average,
                dataset_for_averaging=dataset_for_averaging,
                variable=variable, description=description,
                dataset_store=dataset_store
            ) for group_to_average in groups_to_average)

    averages_table.insert_multiple(records)
    print(averages_table.all())
    print("--- Average %d files by groups, took %s seconds ---\n" %
          (n_files, (time.time() - start_time)))
    db.close()


def main():

    #file_index = "/home/mrosanes/TOT/BEAMLINES/MISTRAL/DATA/" \
    #             "PARALLEL_IMAGING/image_operate_xrm_test_add/" \
    #             "tests8/xrm/index.json"

    file_index = "/home/mrosanes/TOT/BEAMLINES/MISTRAL/DATA/" \
                 "PARALLEL_IMAGING/PARALLEL_XRM2H5/TOMOFEW/tomo_few/index.json"

    average_images_for_many_img_groups(file_index)
    # sample="ols", energy=640, date=20161203)


if __name__ == "__main__":
    main()