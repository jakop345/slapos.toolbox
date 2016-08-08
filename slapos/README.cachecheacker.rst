HTTP Cache Checker
==================

Crawl a website and check the HTTP configuration.

Run
===

    python2 cachechecker.py -o result.txt cachechecker.conf


Example of configuration
========================

::

    [web_checker]
    url = http://example.org
    
    working_directory = /tmp/cachechecker
    
    # debug_level = info
    debug_level = debug
    file_log_path = /tmp/cachechecker.log
    
    # http://labs.omniti.com/people/mark/ats_sa/slides.html#slide-18
    traffic_server_cache = cHs
      cSsNfU
    
    [header_list]
    Last-Modified = True
    Expires = True
    Vary = Cookie,Authorization,Accept-Encoding
    Cache-Control = max-age=600, stale-while-revalidate=360000, public
    
    [no_header url=.*]
    Set-Cookie = None
    
    [no_header content-type=(image/.*|application/vnd.ms-fontobject|application/x-font-woff|font/truetype)]
    Vary = None
    
    [header content-type=image/.*]
    Cache-Control = max-age=3600, stale-if-error=360000, stale-while-revalidate=360000, public
    
    [header content-type=(text/css|text/plain|application/x-javascript|.*/javascript|application/vnd.ms-fontobject|application/x-font-woff|font/truetype)]
    Vary = Accept-Encoding
    Cache-Control = max-age=3600, stale-if-error=360000, stale-while-revalidate=360000, public
    
    # Captcha
    [header url=(.*/contactus$)]
    Cache-Control = max-age=0, no-cache
    
    # # IE PDF Bug
    [header url=.*format=pdf]
    Cache-Control = Private
    
    [header url=.*format=]
    Vary = Cookie,Authorization,Accept-Encoding
    Cache-Control = max-age=600, stale-while-revalidate=360000, public
    
    [erp5_extension_list]
    prohibited_folder_name_list = web_page_module
      document_module
      web_site_module
    prohibited_file_name_list = WebSection_viewAsWeb
      Base_viewHistory
      Base_download
      list
