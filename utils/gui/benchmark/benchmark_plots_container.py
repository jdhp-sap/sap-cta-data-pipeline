# -*- coding: utf-8 -*-

# Copyright (c) 2015 Jérémie DECOCK (http://www.jdhp.org)

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
See: http://gtk3-matplotlib-cookbook.readthedocs.org/en/latest/
     http://matplotlib.org/1.4.2/examples/user_interfaces/index.html
"""

from gi.repository import Gtk as gtk

import datetime
import math
import numpy as np
import os
import time

import matplotlib.pyplot as plt

from matplotlib.backends.backend_gtk3cairo import FigureCanvasGTK3Cairo as FigureCanvas

from datapipe.io import images
from datapipe.denoising import tailcut as tailcut_mod
from datapipe.denoising import wavelets_mrfilter as wavelets_mod
from datapipe.benchmark import assess as assess_mod

###############################################################################

DEFAULT_COLOR_MAP = "gnuplot2" # "gray"

# histogram types : [‘bar’ | ‘barstacked’ | ‘step’ | ‘stepfilled’]
HISTOGRAM_TYPE = 'bar'

#IMAGE_INTERPOLATION = 'bilinear'   # "smooth" map
IMAGE_INTERPOLATION = 'nearest'    # "raw" (non smooth) map

###############################################################################

class BenchmarkPlotsContainer(gtk.Box):

    def __init__(self, input_directory_path):

        super(BenchmarkPlotsContainer, self).__init__(orientation=gtk.Orientation.VERTICAL, spacing=6)

        self.input_directory_path = input_directory_path
        self.current_file_path = None
        self.kill_isolated_pixels = False

        # Box attributes ##############

        self.set_border_width(18)

        # Matplotlib ##################

        self.fig = plt.figure()

        self.color_map = DEFAULT_COLOR_MAP
        self.show_color_bar = True

        # Entry #######################

        self.wavelets_options_entry = gtk.Entry()
        self.wavelets_options_entry.set_text("-K -k -C1 -m3 -s3 -n4")
        self.wavelets_options_entry.connect("activate", self.update_plots)  # call "print_text()" function when the "Enter" key is pressed in the entry

        # Kill isolated pixels ########

        self.kill_isolated_pixels_switch = gtk.Switch()
        self.kill_isolated_pixels_switch.connect("notify::active", self.kill_isolated_pixels_switch_callback)
        self.kill_isolated_pixels_switch.set_active(False)

        kill_isolated_pixels_label = gtk.Label(label="Kill isolated pixels")

        # Fill the box container ######

        wavelets_options_horizontal_box = gtk.Box(orientation = gtk.Orientation.HORIZONTAL, spacing=6)   # 6 pixels are placed between children
        wavelets_options_horizontal_box.pack_start(self.wavelets_options_entry, expand=True, fill=True, padding=0)
        wavelets_options_horizontal_box.pack_start(kill_isolated_pixels_label, expand=False, fill=False, padding=0)
        wavelets_options_horizontal_box.pack_start(self.kill_isolated_pixels_switch, expand=False, fill=False, padding=0)

        canvas = FigureCanvas(self.fig)
        self.pack_start(canvas, expand=True, fill=True, padding=0)
        self.pack_start(wavelets_options_horizontal_box, expand=False, fill=False, padding=0)


    def kill_isolated_pixels_switch_callback(self, data=None, param=None):
        if self.kill_isolated_pixels_switch.get_active():
            self.kill_isolated_pixels = True
        else:
            self.kill_isolated_pixels = False
        self.update_plots()
    

    def selection_changed_callback(self, file_name):
        self.current_file_path = os.path.join(self.input_directory_path, file_name)
        self.update_plots()


    def update_plots(self, data=None):        # data is for event callers

        if self.current_file_path is not None:
            # Read the selected file #########

            fits_images_dict, fits_metadata_dict = images.load_benchmark_images(self.current_file_path)

            input_img = fits_images_dict["input_image"]
            reference_img = fits_images_dict["reference_image"]

            if input_img.ndim != 2:
                raise Exception("Unexpected error: the input FITS file should contain a 2D array.")

            if reference_img.ndim != 2:
                raise Exception("Unexpected error: the input FITS file should contain a 2D array.")

            # Tailcut #####################

            #input_img_copy = copy.deepcopy(input_img)
            input_img_copy = input_img.astype('float64', copy=True)

            tailcut = tailcut_mod.Tailcut()
            
            initial_time = time.perf_counter()
            tailcut_cleaned_img = tailcut.clean_image(input_img_copy, high_threshold=10, low_threshold=5)
            tailcut_execution_time = time.perf_counter() - initial_time

            # Wavelets ####################

            #input_img_copy = copy.deepcopy(input_img)
            input_img_copy = input_img.astype('float64', copy=True)

            wavelets = wavelets_mod.WaveletTransform()

            option_string = self.wavelets_options_entry.get_text()
            print(option_string)
            
            initial_time = time.perf_counter()
            wavelets_cleaned_img = wavelets.clean_image(input_img_copy,
                                                        kill_isolated_pixels=self.kill_isolated_pixels,
                                                        verbose=True,
                                                        raw_option_string=option_string)
            wavelets_execution_time = time.perf_counter() - initial_time

            # Execution time ##############

            print("Tailcut execution time: ", tailcut_execution_time) # TODO
            print("Wavelets execution time: ", wavelets_execution_time) # TODO

            # Tailcut scores ##############

            try:
                tailcut_score_tuple, tailcut_score_name_tuple = assess_mod.assess_image_cleaning(input_img,
                                                                                                 tailcut_cleaned_img,
                                                                                                 reference_img,
                                                                                                 benchmark_method="all")
                print("TC:", tailcut_score_tuple, tailcut_score_name_tuple)
            except assess_mod.AssessError:
                print("TC: ", str(assess_mod.AssessError))

            # Wavelets scores #############

            try:
                wavelets_score_tuple, wavelets_score_name_tuple = assess_mod.assess_image_cleaning(input_img,
                                                                                                   wavelets_cleaned_img,
                                                                                                   reference_img,
                                                                                                   benchmark_method="all")

                print("WT:", wavelets_score_tuple, wavelets_score_name_tuple)
            except assess_mod.AssessError:
                print("WT: ", str(assess_mod.AssessError))

            # Update the widget ###########

            self.clear_figure()

            ax1 = self.fig.add_subplot(221)
            ax2 = self.fig.add_subplot(222)
            ax3 = self.fig.add_subplot(223)
            ax4 = self.fig.add_subplot(224)

            self._draw_image(ax1, input_img, "Input")
            self._draw_image(ax2, reference_img, "Reference")
            self._draw_image(ax3, tailcut_cleaned_img, "Tailcut")
            self._draw_image(ax4, wavelets_cleaned_img, "Wavelets")

            #self._draw_histogram(ax1, input_img, "Input")
            #self._draw_histogram(ax2, reference_img, "Reference")
            #self._draw_histogram(ax3, tailcut_cleaned_img, "Tailcut")
            #self._draw_histogram(ax4, wavelets_cleaned_img, "Wavelets")

            self.fig.canvas.draw()


    def clear_figure(self):
        self.fig.clf()
        self.fig.canvas.draw()


    def _draw_image(self, axis, image_array, title):

        # See http://matplotlib.org/examples/pylab_examples/pcolor_demo.html

        dx, dy = 1, 1

        # generate 2 2d grids for the x & y bounds
        y, x = np.mgrid[slice(0, image_array.shape[0], dy), slice(0, image_array.shape[1], dx)]  # TODO !!!

        z_min, z_max = image_array.min(), image_array.max()

        im = axis.pcolor(x, y, image_array, cmap=self.color_map, vmin=z_min, vmax=z_max)

        if self.show_color_bar:
            plt.colorbar(im, ax=axis)

        axis.set_title(title)

        # IMSHOW DOESN'T WORK WITH PYTHON GTK3 THROUGH CAIRO (NOT IMPLEMENTED ERROR) !
        #im = axis.imshow(image_array)
        #im = axis.imshow(image_array,
        #                 origin='lower',
        #                 interpolation=IMAGE_INTERPOLATION,
        #                 cmap=self.color_map)
        #axis.set_axis_off()
        #if self.show_color_bar:
        #    plt.colorbar(im) # draw the colorbar


    def _draw_histogram(self, axis, image_array):

        #axis.set_title(self.file_path)
        bins = math.ceil(image_array.max() - image_array.min())

        # nparray.ravel(): Return a flattened array.
        values, bins, patches = axis.hist(image_array.ravel(),
                                          histtype=HISTOGRAM_TYPE,
                                          bins=bins,
                                          #range=(0., 255.),
                                          fc='k',
                                          ec='k')

        axis.set_xlim([image_array.min(), image_array.max()])