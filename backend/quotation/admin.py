from django.contrib import admin

from quotation.models import (
    DocumentAsset,
    FeishuConnection,
    Quotation,
    QuotationItem,
    QuotationVersion,
    UserQuotationCatalog,
)

admin.site.register(Quotation)
admin.site.register(QuotationItem)
admin.site.register(QuotationVersion)
admin.site.register(DocumentAsset)
admin.site.register(FeishuConnection)
admin.site.register(UserQuotationCatalog)
