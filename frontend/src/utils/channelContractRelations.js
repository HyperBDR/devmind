export function offeringsForModel({
  offerings,
  versions,
  priceItems,
  modelId
}) {
  const relatedIds = new Set(
    versions
      .filter((version) => sameId(version.model, modelId))
      .map((version) => String(version.offering))
  )
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

export function currentContractVersion(versions, offeringId, now = Date.now()) {
  return versions
    .filter((version) => {
      if (!sameId(version.offering, offeringId)) return false
      if (!['active', 'scheduled'].includes(version.status)) return false
      const start = version.effective_from
        ? new Date(version.effective_from).getTime()
        : Number.POSITIVE_INFINITY
      const end = version.effective_to
        ? new Date(version.effective_to).getTime()
        : Number.POSITIVE_INFINITY
      return start <= now && now < end
    })
    .sort((left, right) => Number(right.version) - Number(left.version))[0]
}

export function futureContractVersion(versions, offeringId, now = Date.now()) {
  return versions
    .filter(
      (version) =>
        sameId(version.offering, offeringId) &&
        version.effective_from &&
        new Date(version.effective_from).getTime() > now
    )
    .sort(
      (left, right) =>
        new Date(left.effective_from).getTime() -
        new Date(right.effective_from).getTime()
    )[0]
}

function sameId(left, right) {
  return String(left) === String(right)
}
