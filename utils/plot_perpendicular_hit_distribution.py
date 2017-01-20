#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2016 Jérémie DECOCK (http://www.jdhp.org)

# This script is provided under the terms and conditions of the MIT license:
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
Plot a FITS file.

Example usages:
  ./utils/plot_image.py -h
  ./utils/plot_image.py ./test.fits
  ipython3 -- ./utils/plot_image.py ./test.fits
"""

import common_functions as common

import argparse
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from matplotlib.colors import LogNorm

import copy

from datapipe.io import images

from ctapipe.utils import linalg

import astropy.units as u
from ctapipe.image.hillas import hillas_parameters_1 as hillas_parameters_1
from ctapipe.image.hillas import hillas_parameters_2 as hillas_parameters_2


COLOR_MAP = "gnuplot2" # "gray"

def plot_image(axis, image_array, title, plot_log_scale=True):

    #im = axis.imshow(image_array,
    #                 origin='lower',
    #                 interpolation='nearest',
    #                 vmin=min(image_array.min(), 0),
    #                 cmap=COLOR_MAP)

    # See http://matplotlib.org/examples/pylab_examples/pcolor_demo.html

    dx, dy = 1, 1

    # generate 2 2d grids for the x & y bounds
    y, x = np.mgrid[slice(0, image_array.shape[0], dy), slice(0, image_array.shape[1], dx)]  # TODO !!!

    z_min, z_max = image_array.min(), image_array.max()

    if plot_log_scale:
        # See http://matplotlib.org/examples/pylab_examples/pcolor_log.html
        #     http://stackoverflow.com/questions/2546475/how-can-i-draw-a-log-normalized-imshow-plot-with-a-colorbar-representing-the-raw
        im = axis.pcolor(x, y, image_array, norm=LogNorm(vmin=0.01, vmax=image_array.max()), cmap=COLOR_MAP)  # TODO: "vmin=0.01" is an arbitrary choice...
    else:
        im = axis.pcolor(x, y, image_array, cmap=COLOR_MAP, vmin=z_min, vmax=z_max)

    plt.colorbar(im, ax=axis) # draw the colorbar

    axis.set_title(title)


def plot_ellipse_shower_on_image(axis, image_array):
    """Based on Fabio's notebook."""

    x = np.arange(0, np.shape(image_array)[0], 1)
    y = np.arange(0, np.shape(image_array)[1], 1)
    xx, yy = np.meshgrid(x, y)

    hillas = hillas_parameters_2(xx.flatten() * u.meter,
                                 yy.flatten() * u.meter,
                                 image_array.flatten())

    centroid = (hillas.cen_x.value, hillas.cen_y.value)
    length = hillas.length.value
    width = hillas.width.value
    angle = hillas.psi.to(u.rad).value    # TODO

    print("centroid:", centroid)
    print("length:",   length)
    print("width:",    width)
    print("angle:",    angle)

    #print("DEBUG:", hillas[7].value, angle, np.degrees(angle))

    ellipse = Ellipse(xy=centroid, width=width, height=length, angle=np.degrees(angle), fill=False, color='red', lw=2)
    axis.axes.add_patch(ellipse)

    title = axis.axes.get_title()
    axis.axes.set_title("{} ({:.2f}°)".format(title, np.degrees(angle)))

    # Plot centroid

    axis.scatter(*centroid)

    # Plot shower axis

    ellipse = Ellipse(xy=centroid, width=width, height=0, angle=np.degrees(angle), fill=False, color='blue', lw=2)
    axis.axes.add_patch(ellipse)

    ellipse = Ellipse(xy=centroid, width=0, height=length, angle=np.degrees(angle), fill=False, color='blue', lw=2)
    axis.axes.add_patch(ellipse)

    # Plot origin axis

    ellipse = Ellipse(xy=centroid, width=10, height=0, angle=0, fill=False, color='black', lw=2)
    axis.axes.add_patch(ellipse)


def plot_perpendicular_hit_distribution(axis, image_array, title):

    ref_image_array, cleaned_image_array = copy.deepcopy(image_array), copy.deepcopy(image_array)

    size_m = 0.2  # Size of the "phase space" in meter

     # TODO: clean these following hard coded values for Astri
    num_pixels_x = 40
    num_pixels_y = 40

    x = np.linspace(-0.142555996776, 0.142555996776, num_pixels_x)
    y = np.linspace(-0.142555996776, 0.142555996776, num_pixels_y)

    #x = np.arange(0, np.shape(ref_image_array)[0], 1)          # TODO: wrong values -10 10 21
    #y = np.arange(0, np.shape(ref_image_array)[1], 1)          # TODO: wrong values  (30, ...)

    xx, yy = np.meshgrid(x, y)

    # Based on Tino's evaluate_cleaning.py (l. 277)
    hillas = {}
    hillas['ref.'] = hillas_parameters_1(xx.flatten() * u.meter,
                                         yy.flatten() * u.meter,
                                         ref_image_array.flatten())[0]
    hillas['cleaned'] = hillas_parameters_1(xx.flatten() * u.meter,
                                            yy.flatten() * u.meter,
                                            cleaned_image_array.flatten())[0]

    for k, signal in {'ref.': ref_image_array, 'cleaned': cleaned_image_array}.items():

        h = hillas[k]

        # p1 = center of the ellipse
        p1_x = h.cen_x
        p1_y = h.cen_y

        # p2 = intersection between the ellipse and the shower track
        p2_x = p1_x + h.length * np.cos(h.psi + np.pi/2)
        p2_y = p1_y + h.length * np.sin(h.psi + np.pi/2)

        # slope of the shower track
        T = linalg.normalise(np.array([p1_x-p2_x, p1_y-p2_y]))

        x = xx.flatten()
        y = yy.flatten()

        # Manhattan distance of pixels to the center of the ellipse
        D = [p1_x-x, p1_y-y]

        # Pixels in the new base
        dl = D[0]*T[0] + D[1]*T[1]
        dp = D[0]*T[1] - D[1]*T[0]

        # nparray.ravel(): Return a flattened array.
        values, bins, patches = axis.hist(dp.ravel(),
                                          histtype='step',
                                          label=k,
                                          bins=np.linspace(-size_m, size_m, 31))          # -10 10 21
    
    axis.set_xlim([-size_m, size_m])

    axis.set_xlabel('Distance to the shower axis (m)', fontsize=14)
    axis.set_ylabel('Hits', fontsize=14)

    axis.legend(prop={'size': 16}, loc='lower center')
    axis.set_title(title)


def main():

    # PARSE OPTIONS ###########################################################

    parser = argparse.ArgumentParser(description="Plot a FITS file.")

    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Don't show the plot, just save it")

    parser.add_argument("--output", "-o", default=None, metavar="FILE",
                        help="The output file path (image file)")

    parser.add_argument("fileargs", nargs="+", metavar="FILE",
                        help="The files image to process (FITS)."
                             "If fileargs is a directory,"
                             "all FITS files it contains are processed.")

    args = parser.parse_args()

    quiet = args.quiet
    output = args.output
    input_file_or_dir_path_list = args.fileargs

    # FETCH IMAGES ############################################################

    for input_file_or_dir_path in input_file_or_dir_path_list:

        if os.path.isdir(input_file_or_dir_path):
            input_file_path_list = common.get_fits_files_list(input_directory_path)
        else:
            input_file_path_list = [input_file_or_dir_path]

        # Parse FITS files
        for input_file_path in input_file_path_list:

            # READ THE INPUT FILE #############################################

            fits_images_dict, fits_metadata_dict = images.load_benchmark_images(input_file_path)

            input_img = fits_images_dict["input_image"]
            reference_img = fits_images_dict["reference_image"]

            if input_img.ndim != 2:
                raise Exception("Unexpected error: the input FITS file should contain a 2D array.")

            if reference_img.ndim != 2:
                raise Exception("Unexpected error: the input FITS file should contain a 2D array.")

            # ASSESS OR PRINT THE CLEANED IMAGE ###############################

            fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2, figsize=(16, 9))

            plot_image(ax1, reference_img, "Reference image")
            plot_ellipse_shower_on_image(ax1, reference_img)

            plot_perpendicular_hit_distribution(ax2, reference_img, "Perpendicular hit distribution")

            # PLOT AND SAVE ###################################################

            base_file_path = os.path.basename(input_file_path)
            base_file_path = os.path.splitext(base_file_path)[0]

            if output is None:
                output = "{}.pdf".format(base_file_path)

            plt.savefig(output, bbox_inches='tight')
    
            if not quiet:
                plt.show()


if __name__ == "__main__":
    main()

