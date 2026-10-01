"""Content-shape contract shared across the pipeline.

`PageContent` defines the structured fields a page carries once read from the local
source. A content-source adapter (agentshield/sources/) populates this shape from
the project's files or database. The `type` field (product/article/other) comes
from the source configuration, and `normalize_content()` maps loose fields onto
these names. `additional_labels` holds any other labels present on the page.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PageContent(BaseModel):
    type: Literal["product", "article", "other"] = Field(
        ...,
        description="Page type: 'product', 'article', or 'other' (no prompt is injected into "
                    "'other' pages).")
    title: Optional[str] = Field(None, description="The main title of the page")
    description: Optional[str] = Field(
        None,
        description="For a product, the product description; for an article, the body text.")

    # --- product fields (fill only when type == 'product') ---
    price: Optional[str] = Field(
        None, description="Product only: the current selling price with currency symbol")
    regular_price: Optional[str] = Field(
        None, description="Product only: the original price if on sale, with currency symbol")
    sale_price: Optional[str] = Field(
        None, description="Product only: the sale price if on sale, with currency symbol")
    shipping: Optional[str] = Field(
        None, description="Product only: shipping info if shown, e.g. 'Free Shipping'")
    sku: Optional[str] = Field(None, description="Product only: SKU or item code if shown")
    availability: Optional[str] = Field(
        None, description="Product only: stock/availability status, e.g. 'In stock'")
    rating: Optional[str] = Field(None, description="Product only: customer rating if shown")
    categories: List[str] = Field(
        default_factory=list, description="Product only: categories or tags listed on the page")

    # --- article fields (fill only when type == 'article') ---
    summary: Optional[str] = Field(None, description="Article only: a short summary if present")
    author: Optional[str] = Field(None, description="Article only: the author if shown")
    date_published: Optional[str] = Field(None, description="Article only: publication date if shown")
    tags: List[str] = Field(
        default_factory=list, description="Article only: tags or categories listed on the page")

    # --- catch-all ---
    additional_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="Any other labels/attributes/metadata actually present on the page, as "
                    "key-value pairs. Only include what is genuinely on the page.")
