from pydantic import BaseModel, Field


class ExtractedCatalogItem(BaseModel):
    model_name: str = Field(description="Canonical model name as shown by the vendor.")
    aliases: list[str] = Field(default_factory=list, description="Optional aliases found on the page.")
    family: str | None = Field(default=None, description="Optional model family/category.")
    input_price_per_million: float | None = Field(
        default=None,
        description="Input token price normalized to the vendor currency per 1 million tokens.",
    )
    output_price_per_million: float | None = Field(
        default=None,
        description="Output token price normalized to the vendor currency per 1 million tokens.",
    )
    currency: str = Field(default="USD", description="Currency code for the extracted prices.")
    market_scope: str | None = Field(
        default=None,
        description="Optional market/region scope like domestic or international.",
    )
    notes: str | None = Field(default=None, description="Short note about normalization or missing data.")


class ExtractedPricingCatalog(BaseModel):
    models: list[ExtractedCatalogItem] = Field(
        default_factory=list,
        description="All supported priced models extracted from the source document.",
    )
    notes: str | None = Field(default=None, description="Short summary of extraction assumptions.")
