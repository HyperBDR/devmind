from unittest import TestCase

from ai_assistant.contracts import AssistantTool
from ai_assistant.provider import AssistantCapabilityProvider


class AssistantCapabilityProviderTests(TestCase):
    def test_provider_requires_instructions_and_tools_contracts(self):
        class IncompleteProvider(AssistantCapabilityProvider):
            app_key = "incomplete"
            display_name = "Incomplete"
            required_feature = "incomplete"

        with self.assertRaises(TypeError):
            IncompleteProvider()

    def test_provider_builds_stable_capability_contract(self):
        tool = AssistantTool(
            name="example_query",
            description="Query example data.",
            schema={"type": "object", "properties": {}},
            handler=lambda context, arguments: {"ok": True},
        )

        class ExampleProvider(AssistantCapabilityProvider):
            app_key = "example"
            display_name = "Example Assistant"
            required_feature = "example"
            description = "Example capability."

            def get_instructions(self):
                return "Use example tools only."

            def get_tools(self):
                return (tool,)

        capability = ExampleProvider().build_capability()

        self.assertEqual(capability.app_key, "example")
        self.assertEqual(capability.display_name, "Example Assistant")
        self.assertEqual(capability.instructions, "Use example tools only.")
        self.assertEqual(capability.tools, (tool,))

    def test_provider_rejects_missing_required_metadata(self):
        class InvalidProvider(AssistantCapabilityProvider):
            def get_instructions(self):
                return "Instructions"

            def get_tools(self):
                return ()

        with self.assertRaisesRegex(
            ValueError,
            "app_key, display_name and required_feature",
        ):
            InvalidProvider().build_capability()
