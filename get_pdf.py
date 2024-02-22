#!/usr/bin/env python3
try:
    import cgi
    import cgitb
    import sys

    from pdf_stamp import *

    cgitb.enable()

    data = sys.stdin.buffer.read()

    pdf, certs = read_zip(data)

    images = get_images(pdf)
    draw_stamps(images[-1], certs)
    html = get_html(images)

except Exception as e:
    html = str(e)

print('Content-Type: text/plain\r\n\r\n', end='')
print(html)