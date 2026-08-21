<template>
  <section class="price-meaning-guide" :aria-labelledby="titleId">
    <div class="price-meaning-guide-header">
      <div>
        <p class="price-meaning-guide-kicker">
          {{ t('llmOps.priceMeaningGuide.kicker') }}
        </p>
        <h4 :id="titleId" class="price-meaning-guide-title">
          {{ t('llmOps.priceMeaningGuide.title') }}
        </h4>
        <p class="price-meaning-guide-description">
          {{ t('llmOps.priceMeaningGuide.description') }}
        </p>
      </div>
      <span class="price-meaning-guide-badge" aria-hidden="true">i</span>
    </div>

    <div class="price-meaning-guide-grid">
      <div class="price-meaning-guide-item">
        <strong>{{ t('llmOps.priceMeaningGuide.inputLabel') }}</strong>
        <span>{{ t('llmOps.priceMeaningGuide.input') }}</span>
      </div>
      <div class="price-meaning-guide-item">
        <strong>{{ t('llmOps.priceMeaningGuide.outputLabel') }}</strong>
        <span>{{ t('llmOps.priceMeaningGuide.output') }}</span>
      </div>
      <div class="price-meaning-guide-item">
        <strong>{{ t('llmOps.priceMeaningGuide.cacheLabel') }}</strong>
        <span>{{ t('llmOps.priceMeaningGuide.cache') }}</span>
      </div>
    </div>

    <div class="price-meaning-guide-flow" role="list">
      <span role="listitem">{{ t('llmOps.priceMeaningGuide.upstream') }}</span>
      <span class="price-meaning-guide-arrow" aria-hidden="true">→</span>
      <span role="listitem">{{
        t('llmOps.priceMeaningGuide.channelCost')
      }}</span>
      <span class="price-meaning-guide-arrow" aria-hidden="true">→</span>
      <span role="listitem">{{
        t('llmOps.priceMeaningGuide.listingPrice')
      }}</span>
    </div>

    <p class="price-meaning-guide-formula">
      {{ t('llmOps.priceMeaningGuide.formula') }}
    </p>
  </section>
</template>

<script setup>
import { getCurrentInstance } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const instance = getCurrentInstance()
const titleId = `price-meaning-guide-${instance?.uid || 'shared'}`
</script>

<style scoped>
.price-meaning-guide {
  border: 1px solid rgb(199 210 254);
  border-radius: 0.75rem;
  background: rgb(238 242 255 / 0.72);
  padding: 0.875rem 1rem;
}

.price-meaning-guide-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.price-meaning-guide-kicker {
  color: rgb(79 70 229);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.price-meaning-guide-title {
  margin-top: 0.125rem;
  color: rgb(30 41 59);
  font-size: 0.875rem;
  font-weight: 700;
}

.price-meaning-guide-description {
  margin-top: 0.25rem;
  color: rgb(71 85 105);
  font-size: 0.75rem;
  line-height: 1.5;
}

.price-meaning-guide-badge {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  border: 1px solid rgb(129 140 248);
  border-radius: 9999px;
  color: rgb(67 56 202);
  font-size: 0.75rem;
  font-weight: 700;
}

.price-meaning-guide-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.price-meaning-guide-item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
  padding: 0.5rem 0.625rem;
  border: 1px solid rgb(224 231 255);
  border-radius: 0.5rem;
  background: rgb(255 255 255 / 0.72);
}

.price-meaning-guide-item strong {
  color: rgb(30 41 59);
  font-size: 0.75rem;
}

.price-meaning-guide-item span {
  color: rgb(71 85 105);
  font-size: 0.6875rem;
  line-height: 1.45;
}

.price-meaning-guide-flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.75rem;
  color: rgb(51 65 85);
  font-size: 0.6875rem;
  font-weight: 600;
}

.price-meaning-guide-flow > span:not(.price-meaning-guide-arrow) {
  padding: 0.25rem 0.5rem;
  border-radius: 0.375rem;
  background: rgb(255 255 255 / 0.76);
}

.price-meaning-guide-arrow {
  color: rgb(99 102 241);
  font-size: 0.875rem;
}

.price-meaning-guide-formula {
  margin-top: 0.625rem;
  color: rgb(51 65 85);
  font-size: 0.6875rem;
  line-height: 1.5;
}

@media (max-width: 640px) {
  .price-meaning-guide-grid {
    grid-template-columns: 1fr;
  }
}
</style>
