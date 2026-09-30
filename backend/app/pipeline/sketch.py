"""Sketch input: an inventor's rough drawing or prototype photo, read into
parts and connections they can check before anything is searched.

Many grassroots inventors think in drawings, not patent prose. A photo of a
hand-drawn sketch is a faster, more honest starting point than a paragraph
they struggle to write. But a vision model misreads rough drawings (is that
line a pipe or a label arrow?), so its reading is never searched directly:
it comes back as editable structure — parts, how they connect, and the
questions the model couldn't answer from the image — and the inventor
corrects it first. The frontend turns the corrected structure into the idea
text the normal pipeline runs on.

The model is asked to describe only what the image shows or its labels say.
Its output is still validated here: connections must join two real parts,
duplicates and empties are dropped, and an image with no identifiable parts
is refused with a message the inventor can act on.
"""
import base64
import binascii
import re

from pydantic import BaseModel, ValidationError

from app.llm import complete_json_with_image

MAX_COMPONENTS = 10
MAX_RELATIONSHIPS = 12
MAX_UNCERTAIN = 4
# Groq accepts base64 images up to 4 MB; the frontend downscales well below
# this, so anything larger was not sent by it.
MAX_IMAGE_BYTES = 3_500_000
ALLOWED_IMAGE_TYPES = ("png", "jpeg", "webp")

_COMPONENT_ID = re.compile(r"\bC\d+\b", re.IGNORECASE)
_DATA_URL = re.compile(r"^data:image/(?P<type>[a-z]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$")


class SketchUnreadable(ValueError):
    """The image can't be used — the message says why, for the inventor."""


class SketchComponent(BaseModel):
    id: str  # "C1"
    name: str
    description: str


class SketchRelationship(BaseModel):
    source: str  # component id
    target: str  # component id
    relation: str  # "sits inside", "drains into"


class SketchReading(BaseModel):
    purpose: str
    components: list[SketchComponent]
    relationships: list[SketchRelationship]
    # What the model couldn't make out, as questions for the inventor.
    uncertain: list[str]


PROMPT = """This image is an inventor's rough sketch, labelled drawing, or photo of a \
prototype of their invention.
{note_block}
Read it the way a patent searcher would, and report:
- "purpose": one sentence on what the invention is for. "" if the image doesn't show it.
- "components": the distinct physical parts (2-{max_components}), each \
{{"id": "C1", "name": "<short noun phrase>", "description": "<one sentence: what it is, \
what it seems to be made of, what it does>"}}. Use the drawing's own written labels as \
names when it has them.
- "relationships": how the parts are arranged or work together, each {{"source": "C1", \
"target": "C2", "relation": "<short verb phrase, e.g. sits inside, is filled with, \
drains into, is hinged to>"}}.
- "uncertain": up to {max_uncertain} short questions about details you could not make out \
from the image and that matter for how it works (e.g. "Is the outer pot glazed or unglazed?").

Describe only what the image shows or its labels say. Do not add features, materials or \
benefits that aren't visible. Describe the invention, not the drawing: write "a damp cloth \
draped over the top", never "a dashed line indicating a covering", and never mention \
labels, lines or how something is depicted. If the image does not show a device, object or process, \
return an empty "components" list.

Respond with a single JSON object:
{{"purpose": "...", "components": [{{"id": "C1", "name": "...", "description": "..."}}], \
"relationships": [{{"source": "C1", "target": "C2", "relation": "..."}}], "uncertain": ["..."]}}
"""

NOTE_BLOCK = """The inventor added this note (it may be in any language; use it to \
interpret the image, but describe the image, not the note):
---
{note}
---
"""


class _RawComponent(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""


class _RawRelationship(BaseModel):
    source: str = ""
    target: str = ""
    relation: str = ""


class _RawReading(BaseModel):
    purpose: str = ""
    components: list[_RawComponent] = []
    relationships: list[_RawRelationship] = []
    uncertain: list[str] = []


def decode_image(data_url: str) -> bytes:
    """The image bytes from a data URL, or SketchUnreadable. The data URL is
    what gets sent on to the model, so it's checked here first: a supported
    type, valid base64, and a size the provider will accept."""
    match = _DATA_URL.match(data_url.strip())
    if not match:
        raise SketchUnreadable("That file isn't an image we can read. Upload a PNG, JPEG or WebP.")
    if match.group("type") not in ALLOWED_IMAGE_TYPES:
        raise SketchUnreadable("Upload the sketch as a PNG, JPEG or WebP image.")
    try:
        data = base64.b64decode(match.group("data"), validate=False)
    except (binascii.Error, ValueError):
        raise SketchUnreadable("That image couldn't be decoded. Try uploading it again.")
    if not data:
        raise SketchUnreadable("That image is empty. Try uploading it again.")
    if len(data) > MAX_IMAGE_BYTES:
        raise SketchUnreadable("That image is too large. Try a smaller photo (under 3 MB).")
    return data


def build_reading(raw: _RawReading) -> SketchReading:
    """Keep only what holds together: named parts (renumbered C1..Cn),
    connections between two distinct known parts, and non-empty questions."""
    components: list[SketchComponent] = []
    new_id: dict[str, str] = {}
    seen_names: set[str] = set()
    for c in raw.components:
        name = " ".join(c.name.split())
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())
        component_id = f"C{len(components) + 1}"
        if c.id.strip():
            new_id.setdefault(c.id.strip().upper(), component_id)
        components.append(
            SketchComponent(id=component_id, name=name, description=" ".join(c.description.split()))
        )
        if len(components) == MAX_COMPONENTS:
            break

    if not components:
        raise SketchUnreadable(
            "We couldn't make out any parts in that image. Try a clearer photo, or add labels "
            "to the drawing."
        )

    # Models sometimes name a part by its id inside the relation text
    # ("fills the gap between the pot and C1"); the inventor sees the name.
    name_by_raw_id = {raw_id: components[int(new[1:]) - 1].name for raw_id, new in new_id.items()}

    def named(text: str) -> str:
        return _COMPONENT_ID.sub(lambda m: name_by_raw_id.get(m.group(0).upper(), m.group(0)), text)

    relationships: list[SketchRelationship] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for r in raw.relationships:
        source = new_id.get(r.source.strip().upper())
        target = new_id.get(r.target.strip().upper())
        relation = named(" ".join(r.relation.split()))
        if not source or not target or source == target or not relation:
            continue
        key = (source, target, relation.lower())
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        relationships.append(SketchRelationship(source=source, target=target, relation=relation))
        if len(relationships) == MAX_RELATIONSHIPS:
            break

    uncertain = [q.strip() for q in raw.uncertain if q.strip()][:MAX_UNCERTAIN]
    return SketchReading(
        purpose=" ".join(raw.purpose.split()),
        components=components,
        relationships=relationships,
        uncertain=uncertain,
    )


def read_sketch(image_data_url: str, note: str | None = None) -> SketchReading:
    """Raises SketchUnreadable for an image the inventor needs to replace,
    and ValueError when the model fails (worth a retry)."""
    decode_image(image_data_url)
    note = (note or "").strip()
    prompt = PROMPT.format(
        note_block=NOTE_BLOCK.format(note=note) if note else "",
        max_components=MAX_COMPONENTS,
        max_uncertain=MAX_UNCERTAIN,
    )
    last_error: Exception | None = None
    for _ in range(2):
        try:
            raw = _RawReading.model_validate(complete_json_with_image(prompt, image_data_url.strip()))
        except (ValueError, ValidationError) as e:
            last_error = e
            continue
        return build_reading(raw)
    raise ValueError(f"Sketch reading failed: {last_error}")
