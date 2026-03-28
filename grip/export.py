"""
Export markdown to a self-contained HTML file.
"""

import html
import io
import os
import sys

from .config import CDN_ASSETS


EXPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" data-color-mode="{data_color_mode}" data-light-theme="light" data-dark-theme="dark">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
{head_assets}
  <style>
    .preview-page {{ margin-top: 64px; margin-bottom: 21px; }}
    .timeline-comment-wrapper > .timeline-comment:after,
    .timeline-comment-wrapper > .timeline-comment:before {{ content: none; }}
    .discussion-timeline.wide {{ width: 920px; }}
  </style>
</head>
<body>
  <div class="page">
    <div class="preview-page">
      <main id="js-repo-pjax-container">
        <div class="clearfix new-discussion-timeline container-xl px-3 px-md-4 px-lg-5">
          <div class="repository-content">
            <div class="clearfix">
              <div class="Layout Layout--flowRow-until-md Layout--sidebarPosition-end Layout--sidebarPosition-flowRow-end">
                <div class="Layout-main">
{page_body}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>
  <script id="grip-source" type="text/markdown">{escaped_markdown}</script>
{script_assets}
  <script>
{grip_js}
  </script>
</body>
</html>"""

README_BODY = """\
                  <div id="readme" class="Box md Box--responsive">
                    {box_header}
                    <div class="Box-body px-5 pb-5">
                      <article id="grip-content" class="markdown-body entry-content container-lg">
                      </article>
                    </div>
                  </div>"""

USER_CONTENT_BODY = """\
                  <div class="pull-discussion-timeline">
                    <div class="ml-0 pl-0 ml-md-6 pl-md-3">
                      <div class="TimelineItem pt-0">
                        <div class="timeline-comment-group TimelineItem-body my-0">
                          <div class="ml-n3 timeline-comment unminimized-comment comment">
                            {comment_header}
                            <div class="edit-comment-hide">
                              <table class="d-block">
                                <tbody class="d-block">
                                  <tr class="d-block">
                                    <td class="d-block comment-body markdown-body" id="grip-content">
                                    </td>
                                  </tr>
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>"""

GRIP_JS_DIR = os.path.join(os.path.dirname(__file__), 'static')


def export_page(reader, subpath, assets, out_file=None, inline=True,
                title=None, theme='light', user_content=False,
                wide=False, quiet=False):
    """Export a rendered markdown page to HTML.

    If out_file is '-', writes to stdout.
    If out_file is None, returns the HTML string.
    """
    text = reader.read(subpath)
    filename = reader.filename_for(subpath) or ''

    page_title = title if title else (filename + ' - Grip' if filename else 'Grip')
    display_title = html.escape(title or filename)
    data_color_mode = 'dark' if theme == 'dark' else 'light'

    # Page body
    if user_content:
        comment_header = ''
        if display_title:
            comment_header = (
                '<div class="timeline-comment-header clearfix d-block d-sm-flex">'
                '<h3 class="timeline-comment-header-text f5 text-normal">'
                '<strong class="css-truncate expandable">'
                '<span class="author text-inherit css-truncate-target">'
                '{0}</span></strong></h3></div>'.format(display_title))
        page_body = USER_CONTENT_BODY.format(comment_header=comment_header)
    else:
        box_header = ''
        if display_title:
            box_header = (
                '<div class="Box-header d-flex border-bottom-0 flex-items-center'
                ' flex-justify-between color-bg-default rounded-top-2">'
                '<div class="d-flex flex-items-center">'
                '<h2 class="Box-title">{0}</h2>'
                '</div></div>'.format(display_title))
        page_body = README_BODY.format(box_header=box_header)

    # Escape markdown for embedding in <script> tag
    escaped_markdown = text.replace('</script', '<\\/script')

    highlight_css_name = ('github-highlight-dark.min.css'
                          if theme == 'dark' else
                          'github-highlight.min.css')

    if inline:
        # Read all assets and inline them
        css_files = ['github-markdown.css', highlight_css_name]
        js_files = ['marked.min.js', 'highlight.min.js', 'mermaid.min.js']

        head_parts = []
        for css_name in css_files:
            css_path = assets.get_path(css_name)
            if os.path.isfile(css_path):
                with open(css_path, 'r', encoding='utf-8') as f:
                    head_parts.append('  <style>\n' + f.read() + '\n  </style>')
        head_assets = '\n'.join(head_parts)

        script_parts = []
        for js_name in js_files:
            js_path = assets.get_path(js_name)
            if os.path.isfile(js_path):
                with open(js_path, 'r', encoding='utf-8') as f:
                    script_parts.append(
                        '  <script>\n' + f.read() + '\n  </script>')
        script_assets = '\n'.join(script_parts)
    else:
        # Link to CDN
        cdn = CDN_ASSETS
        head_assets = (
            '  <link rel="stylesheet" href="{0}" />\n'
            '  <link rel="stylesheet" href="{1}" />'
        ).format(cdn['github-markdown.css'], cdn[highlight_css_name])

        script_assets = (
            '  <script src="{0}"></script>\n'
            '  <script src="{1}"></script>\n'
            '  <script src="{2}"></script>'
        ).format(cdn['marked.min.js'], cdn['highlight.min.js'],
                 cdn['mermaid.min.js'])

    # Read grip.js
    grip_js_path = os.path.join(GRIP_JS_DIR, 'grip.js')
    with open(grip_js_path, 'r', encoding='utf-8') as f:
        grip_js = f.read()

    page = EXPORT_TEMPLATE.format(
        title=html.escape(page_title),
        data_color_mode=data_color_mode,
        head_assets=head_assets,
        page_body=page_body,
        escaped_markdown=escaped_markdown,
        script_assets=script_assets,
        grip_js=grip_js,
    )

    if out_file == '-':
        print(page)
    elif out_file is not None:
        with io.open(out_file, 'w', encoding='utf-8') as f:
            f.write(page)
    return page
