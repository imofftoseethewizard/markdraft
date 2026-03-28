import html as html_module
import re

from .renderers import OfflineRenderer

MERMAID_BLOCK_RE = re.compile(
    r'(`{3,})mermaid\s*\n(.*?)\1',
    re.DOTALL
)


class GripperRenderer(OfflineRenderer):
    """
    Renders markdown offline with mermaid diagram support.

    Extracts mermaid fenced code blocks before markdown rendering and
    emits them as <pre class="mermaid"> tags for client-side rendering
    by mermaid.js.
    """

    def render(self, text, auth=None):
        blocks = []

        def replacer(match):
            idx = len(blocks)
            blocks.append(match.group(2))
            return 'GRIPPER_MERMAID_{0}'.format(idx)

        text = MERMAID_BLOCK_RE.sub(replacer, text)

        html = super(GripperRenderer, self).render(text, auth)

        for i, mermaid_source in enumerate(blocks):
            placeholder = 'GRIPPER_MERMAID_{0}'.format(i)
            escaped = html_module.escape(mermaid_source)
            mermaid_html = '<pre class="mermaid">{0}</pre>'.format(escaped)
            html = re.sub(
                r'<p>\s*' + re.escape(placeholder) + r'\s*</p>',
                mermaid_html,
                html
            )
            html = html.replace(placeholder, mermaid_html)

        return html
