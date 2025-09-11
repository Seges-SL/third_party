{
    "name": "Server Info",
    "summary": "Settings tab with automatically updated server information",
    "description": """
    This module add new tab 'Server Info' in settings.
    This tab contains automatically updated information about server cpu, ram and disk usage.
    It also allows you to change frequency of information updates.
    """,
    "author": "myOdoo.pl",
    "website": "https://myodoo.pl",
    "category": "Technical",
    "version": "17.0.1.1.0",
    "license": "LGPL-3",
    "images": [
        "static/description/banner.png",
        "static/description/usage.png",
    ],
    "external_dependencies": {"python": ["psutil"]},
    "depends": [
        "base_setup",
        "web",
        "base",
    ],
    "data": [
        "views/settings_views.xml",
        "data/settings_records.xml",

    ],
    "assets": {
        "web.assets_backend": [
            "web/static/src/legacy/js/core/**/*.js",
            "web/static/src/core/*.js",
            "web/static/src/core/utils/*.js",
            "web/static/src/core/network/*.js",
            "web/static/src/*.js",
            "web/static/src/views/**/*.js",
            "server_info/static/src/js/*.js",
            "server_info/static/src/xml/*.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
}
