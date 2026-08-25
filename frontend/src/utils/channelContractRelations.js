export function offeringsForModel({
  offerings,
  priceItems,
  modelId
}) {
  const relatedIds = new Set()
  priceItems
    .filter((item) => sameId(item.model, modelId))
    .forEach((item) => {
      if (item.offering) relatedIds.add(String(item.offering))
    })
  return offerings.filter(
    (offering) =>
      sameId(offering.model, modelId) || relatedIds.has(String(offering.id))
  )
}

function sameId(left, right) {
  return String(left) === String(right)
}
