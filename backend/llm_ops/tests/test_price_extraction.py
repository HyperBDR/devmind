from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from llm_ops.collectors.official import (
    OfficialPriceSpec,
    OfficialProviderConfig,
    config_with_source_prices,
)
from llm_ops.price_extraction import (
    ExtractedModelPrice,
    ExtractedPrice,
    official_specs_to_extracted_model_prices,
    validate_extracted_model_prices,
)


class PriceExtractionValidationTests(SimpleTestCase):
    def test_accepts_deterministic_price_candidate(self):
        candidate = ExtractedModelPrice(
            model_code="gpt-4o",
            currency="USD",
            prices=(
                ExtractedPrice(
                    dimension="input",
                    amount=Decimal("2.50"),
                    unit="per_1m_tokens",
                ),
                ExtractedPrice(
                    dimension="output",
                    amount=Decimal("10"),
                    unit="per_1m_tokens",
                ),
            ),
            parser="deterministic",
            confidence=Decimal("1"),
            evidence="OpenAI pricing table",
        )

        result = validate_extracted_model_prices(
            [candidate],
            allowed_model_codes={"gpt-4o"},
        )

        self.assertEqual(result.accepted, (candidate,))
        self.assertEqual(result.rejected, ())

    def test_rejects_unmapped_model_code(self):
        candidate = ExtractedModelPrice(
            model_code="unknown-model",
            currency="USD",
            prices=(
                ExtractedPrice(
                    dimension="input",
                    amount=Decimal("1"),
                    unit="per_1m_tokens",
                ),
            ),
            parser="deterministic",
            confidence=Decimal("1"),
        )

        result = validate_extracted_model_prices(
            [candidate],
            allowed_model_codes={"gpt-4o"},
        )

        self.assertEqual(result.accepted, ())
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("not in allowed model codes", result.rejected[0].reason)

    def test_rejects_llm_candidate_without_evidence(self):
        candidate = ExtractedModelPrice(
            model_code="gpt-4o",
            currency="USD",
            prices=(
                ExtractedPrice(
                    dimension="input",
                    amount=Decimal("2.50"),
                    unit="per_1m_tokens",
                ),
            ),
            parser="llm",
            confidence=Decimal("0.95"),
        )

        result = validate_extracted_model_prices([candidate])

        self.assertEqual(result.accepted, ())
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("requires evidence", result.rejected[0].reason)

    def test_converts_official_specs_to_price_candidates(self):
        config = SimpleNamespace(
            provider_code="openai",
            source_url="https://openai.com/api/pricing/",
            currency="USD",
        )
        spec = SimpleNamespace(
            model_id="gpt-4o",
            input_per_million=Decimal("2.50"),
            output_per_million=Decimal("10"),
            image_output_per_image=None,
            video_output_prices=(),
            source_model_type="Text",
            source_note="official table",
        )

        candidates = official_specs_to_extracted_model_prices(
            config=config,
            specs=[spec],
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].model_code, "gpt-4o")
        self.assertEqual(candidates[0].currency, "USD")
        self.assertEqual(
            [price.dimension for price in candidates[0].prices],
            ["input", "output"],
        )

    def test_official_source_can_use_llm_fallback_candidates(self):
        config = OfficialProviderConfig(
            provider_code="openai",
            provider_label="OpenAI",
            source_url="https://openai.com/api/pricing/",
            currency="USD",
            models=(
                OfficialPriceSpec(
                    model_id="gpt-4o",
                    aliases=("gpt-4o",),
                    input_per_million=Decimal("0"),
                    output_per_million=Decimal("0"),
                ),
            ),
        )
        candidate = ExtractedModelPrice(
            model_code="gpt-4o",
            currency="USD",
            prices=(
                ExtractedPrice(
                    dimension="input",
                    amount=Decimal("2.50"),
                    unit="per_1m_tokens",
                ),
                ExtractedPrice(
                    dimension="output",
                    amount=Decimal("10"),
                    unit="per_1m_tokens",
                ),
            ),
            parser="llm",
            confidence=Decimal("0.95"),
            evidence="Pricing page says input $2.50 and output $10.",
        )

        with mock.patch(
            "llm_ops.collectors.official.extract_prices_with_llm",
            return_value=(candidate,),
        ):
            parsed_config, payload = config_with_source_prices(
                config,
                {
                    "source_url": "https://openai.com/api/pricing/",
                    "text": "Pricing text without deterministic labels.",
                },
            )

        parsed_spec = parsed_config.models[0]
        self.assertEqual(parsed_spec.input_per_million, Decimal("2.50"))
        self.assertEqual(parsed_spec.output_per_million, Decimal("10"))
        self.assertEqual(payload["llm_assisted_parse_count"], 1)

    def test_official_source_uses_llm_fallback_for_missing_specs(self):
        config = OfficialProviderConfig(
            provider_code="openai",
            provider_label="OpenAI",
            source_url="https://openai.com/api/pricing/",
            currency="USD",
            models=(
                OfficialPriceSpec(
                    model_id="gpt-4o",
                    aliases=("gpt-4o",),
                    input_per_million=Decimal("0"),
                    output_per_million=Decimal("0"),
                ),
                OfficialPriceSpec(
                    model_id="gpt-4o-mini",
                    aliases=("gpt-4o-mini",),
                    input_per_million=Decimal("0"),
                    output_per_million=Decimal("0"),
                ),
            ),
        )
        candidate = ExtractedModelPrice(
            model_code="gpt-4o-mini",
            currency="USD",
            prices=(
                ExtractedPrice(
                    dimension="input",
                    amount=Decimal("0.15"),
                    unit="per_1m_tokens",
                ),
                ExtractedPrice(
                    dimension="output",
                    amount=Decimal("0.60"),
                    unit="per_1m_tokens",
                ),
            ),
            parser="llm",
            confidence=Decimal("0.95"),
            evidence="Mini pricing row says input $0.15 and output $0.60.",
        )

        with mock.patch(
            "llm_ops.collectors.official.extract_prices_with_llm",
            return_value=(candidate,),
        ):
            parsed_config, payload = config_with_source_prices(
                config,
                {
                    "source_url": "https://openai.com/api/pricing/",
                    "text": "gpt-4o input $2 output $8",
                },
            )

        prices = {
            spec.model_id: (
                spec.input_per_million,
                spec.output_per_million,
            )
            for spec in parsed_config.models
        }
        self.assertEqual(prices["gpt-4o"], (Decimal("2"), Decimal("8")))
        self.assertEqual(
            prices["gpt-4o-mini"],
            (Decimal("0.15"), Decimal("0.60")),
        )
        self.assertEqual(payload["llm_assisted_parse_count"], 1)
        self.assertNotIn("source_parse_missing_model_ids", payload)
