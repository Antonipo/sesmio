"""sesmio.email — email component system and rendering pipeline.

Quick start::

    from sesmio.email import Html, Head, Body, Container, Heading, Text, Button, render

    template = Html(
        head=Head(title="Welcome", preview="Thanks for signing up!"),
        body=Body(children=Container(
            children=[
                Heading(text="Hello!"),
                Text(text="Welcome to our platform."),
                Button(href="https://example.com", children="Get started"),
            ]
        )),
    )

    html, text = render(template)
"""

from sesmio.email.components import (
    Body,
    Button,
    CodeBlock,
    Column,
    Component,
    Head,
    Heading,
    Hr,
    Html,
    Img,
    Link,
    Node,
    Preview,
    Raw,
    Row,
    Section,
    Spacer,
    Text,
)
from sesmio.email.preview import render_preview
from sesmio.email.render import render, render_html_fragment

__all__ = [
    # Components
    "Html",
    "Head",
    "Body",
    "Container",
    "Section",
    "Row",
    "Column",
    "Heading",
    "Text",
    "Link",
    "Button",
    "Img",
    "Hr",
    "Spacer",
    "Preview",
    "CodeBlock",
    "Raw",
    "Node",
    "Component",
    # Rendering
    "render",
    "render_html_fragment",
    "render_preview",
]

# Container is imported separately to avoid circular re-export confusion.
from sesmio.email.components import Container  # noqa: E402
