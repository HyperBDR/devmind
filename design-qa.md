# Invoice workspace design QA

## Scope

- Invoice list actions follow the existing Quote list icon-button pattern.
- Invoice details keep the existing in-product Commercial Invoice preview.
- Numbering appears before Product line in the New Invoice form.
- Parsed bank, remittance, and signatory fields render in the original footer.
- New Invoice history suggestions come only from parsed imported invoices.
- Customer and Invoice contact roles remain separate from parse to form fill.
- Bank details use complete parsed account-history selections.

## Visual verification

- [x] No embedded browser PDF viewer is present in the details drawer.
- [x] The details drawer has no edit, copy, issue, or download buttons.
- [x] Imported Invoice actions remain in the list Actions column.
- [x] `Motion010926` displays account, bank, SWIFT, remittance, signer, and
      signer title in the reconstructed document footer.
- [x] Numbering is visibly above Product line on the New Invoice page.
- [x] Existing navigation, typography, card radius, borders, and spacing are
      unchanged.
- [x] Selecting `Ai-T Consulting Services (Pty) Ltd` fills customer contact
      `Vandana / info@aitcs.co.za`, USD, and NET60 without filling the Invoice
      contact fields.
- [x] Selecting the Invoice contact fills
      `Natalie / ecosys@oneprocloud.com` without changing the customer contact.
- [x] Parsed item history fills product, description, and same-currency unit
      price; the verified USD sample filled a unit price of 357.
- [x] Selecting the parsed DBS account fills account name, bank, address,
      account number, bank code, branch code, SWIFT, and remittance instruction
      as one consistent account record.
- [x] Chinese mode shows `联系人姓名`, `联系人邮箱`, `票据经办人`, and
      `票据经办邮箱` without the English contact labels.

## Result

Passed against the running Invoice preview on 2026-09-10. The user's latest
instruction to preserve the original details style supersedes the temporary
embedded-PDF approach. The latest parse-field isolation and create-form history
interactions were verified in the same running preview.
