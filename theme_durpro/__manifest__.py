{
    'name': 'Durpro Theme',
    'description': 'Durpro Adaptation of durpro.',
    'category': 'Theme/Corporate',
    'summary': 'Durpro Adaptation of durpro.',
    'sequence': 110,
    'version': '2.0.1',
    'author': 'Bemade.org.',
    'data': [
        'data/ir_asset.xml',
        'views/images_library.xml',
        'views/customizations.xml',
    ],
    'images': [
        'static/description/durpro_poster.jpg',
        'static/description/durpro_screenshot.jpg',
    ],
    'images_preview_theme': {
        'website.s_cover_default_image': '/theme_durpro/static/src/img/pictures/bg_image_08.jpg',
        'website.s_text_image_default_image': '/theme_durpro/static/src/img/pictures/content_02.jpg',
        'website.s_parallax_default_image': '/theme_durpro/static/src/img/pictures/content_12.jpg',
        'website.s_picture_default_image': '/theme_durpro/static/src/img/pictures/content_04.jpg',
    },
    'snippet_lists': {
        'homepage': ['s_cover', 's_text_image', 's_numbers', 's_picture', 's_comparisons'],
    },
    'depends': ['theme_common'],
    'license': 'LGPL-3',
    'assets': {
        'website.assets_editor': [
            'theme_durpro/static/src/js/tour.js',
        ],
    }
}
