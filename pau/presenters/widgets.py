from paucore.utils.presenters import html


def file_upload_progress(image_name='', uploaded=False):
    hide_progress = 'hide'
    text_class = ''
    if uploaded:
        hide_progress = 'plain'
        text_class = ' text-success'

    return html.div(class_='file-related yui3-u', *[
        html.div(class_='hide', *[(
            html.input(type_='file', name='upload_file', data={'file-upload-input': 1})
        )]),
        html.div(class_='file-preview', data={'image-preview-container': 1}, *[
            html.div(class_=hide_progress, data={'upload-progress': 1}, *[
                html.div(class_='progress', *[
                    html.span(class_='image-name', data={'img-name': 1}, *[
                        html.i(class_='icon icon-remove-sign transition-color muted' + hide_progress, data={'remove-attachment': 1}),
                        html.span(class_='image-name-text' + text_class, data={'text': 1}, *[image_name])
                    ]),
                    html.div(class_='bar', style={'width': '0%'})
                ])
            ])
        ])
    ])
