#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Convert the bytestring data of an ICO file to PNG-format data as a bytestring."""

__all__ = ["ico2png"]

#################################################################### 
#
# © Copyright 2011, Isaac Greenspan
# 
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# 
#################################################################### 


from png import Writer as PNGWriter
from struct import unpack
from StringIO import StringIO

def ico2png(data):
	"""Convert the bytestring data of an ICO file to PNG-format data as a bytestring."""
	# try to extract the 6-byte ICO header
	try:
		header = unpack('<3H', data[0:6])
	except:
		raise TypeError # data is not an ICO
	if header[:2] != (0,1):
		raise TypeError # data is not an ICO

	# the number of images in the file is header[2]
	image_count = header[2]

	# collect the icon directories
	directories = []
	for i in xrange(image_count):
		directory = list(unpack('<4B2H2I', data[6 + 16 * i : 6 + 16 * i + 16]))
		for j in xrange(3):
			if not directory[j]:
				directory[j] = 256
		directories.append(directory)

	# select "best" icon (??)
	directory = max(directories, key=(lambda x:x[0:3]))

	# get data of that image
	width = directory[0]
	height = directory[1]
	offset = directory[7]
	result = {
		'width':width,
		'height':height,
		'colors':directory[2],
		'bytes':directory[6],
		'offset':offset,
		}
	if data[offset:offset+16] == "\211PNG\r\n\032\n":
		# looks like a PNG, so return the data from here out.
		return data[offset:]
	else:
		dib_size = unpack('<I', data[offset:offset+4])[0]
		if dib_size != 40:
			raise TypeError # don't know how to handle an ICO where the DIB isn't 40 bytes
		else:
			dib = unpack('<L2l2H2L2l2L', data[offset:offset+dib_size])
			bits_per_pixel = dib[4]
			bmp_data_bytes = dib[6]
			if bmp_data_bytes == 0:
				bmp_data_bytes = width * height * bits_per_pixel / 8
			if bits_per_pixel <= 8:
				# assemble the color palette
				color_count = 2 ** bits_per_pixel
				raw_colors = [
					unpack('BBBB', data[offset + dib_size + 4 * i : offset + dib_size + 4 * i + 4])
					for i in xrange(0,color_count)
					]
				# the RGBQUAD for each palette color is (blue, green, red, reserved)
				palette = [ tuple([color[x] for x in (2, 1, 0)]) for color in raw_colors ]

				# get the XorMap bits
				xor_data_bits = [
					bit
					for byte in data[
						offset + dib_size + color_count * 4
						: offset + dib_size + color_count * 4 + bmp_data_bytes
						]
					for bit in _bitlist(unpack('B',byte)[0])
					]
				# get the AndMap bits
				and_row_size = ((width + 31) >> 5) << 2
				and_data_bits = [
					bit
					for byte in data[
						offset + dib_size + color_count * 4 + bmp_data_bytes
						: offset + dib_size + color_count * 4 + bmp_data_bytes + and_row_size * height
						]
					for bit in _bitlist(unpack('B',byte)[0])
					]

				# assemble the combined image (with transparency)
				def get_pixel(x,y):
					if and_data_bits[(height - y - 1) * and_row_size * 8 + x] == 1:
						# transparent
						return (0,0,0,0)
					else:
						# use the xor value, made solid
						return palette[_bitlistvalue(
							xor_data_bits[
								bits_per_pixel * ((height - y - 1) * width + x)
								: bits_per_pixel * ((height - y - 1) * width + x) + bits_per_pixel
								]
							)] + (255,)
				pixels = [
					[
						c
						for x in xrange(result['width'])
						for c in get_pixel(x,y)
						]
					for y in xrange(result['height'])
					]
			elif bits_per_pixel == 32:
				raw_pixels = [
					[
						unpack('BBBB', data[offset + dib_size + 4 * (y * width + x) : offset + dib_size + 4 * (y * width + x) + 4])
						for x in xrange(width)
						]
					for y in xrange(height-1, -1, -1)
					]
				pixels = [
					[
						c
						for px in row
						for c in (px[2], px[1], px[0], px[3])
						]
					for row in raw_pixels
					]
			elif bits_per_pixel == 24:
				raw_pixels = [
					[
						unpack('BBB', data[offset + dib_size + 3 * (y * width + x) : offset + dib_size + 3 * (y * width + x) + 3])
						for x in xrange(width)
						]
					for y in xrange(height-1, -1, -1)
					]
				pixels = [
					[
						c
						for px in row
						for c in (px[2], px[1], px[0], 255)
						]
					for row in raw_pixels
					]
			else:
				raise TypeError # don't know how to handle the pixel depth value
					
	out = StringIO()
	w = PNGWriter(result['width'],result['height'],alpha=True)
	w.write(out, pixels)
	return out.getvalue()

#######
# helper functions

def _bitlist(byte):
	return [(byte / 2 ** x) & 1 for x in xrange(7,-1,-1)]
def _bitlistvalue(l):
	return reduce(lambda x, y: 2 * x + y, l, 0)

