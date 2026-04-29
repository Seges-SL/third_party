{
    "name": "No Auto Subscribe Notify",
    "version": "17.0.0.0",
    "summary": "Do not send 'You have been assigned' notification to followers of the document",
    "description": """ 
        Do not send 'You have been assigned' notification to followers of the document.
        You have the option to choose which models will be affected by this functionality.
        """,
    "category": "Mail",
    "author": "Exaly",
    "website": "https://exaly.be/",
    "license": "OPL-1",
    "price": 1.00,
    "currency": "EUR",
    'images': [
        'static/description/main.png',
        'static/description/config.png'
    ],
    "depends": [
        "base_setup",
        "mail",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
