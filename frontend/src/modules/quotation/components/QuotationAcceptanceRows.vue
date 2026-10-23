<script setup lang="ts">
import { computed } from 'vue'
import type { PreviewUser } from '../utils/quotationPreviewModel'

const props = defineProps<{
  issuerCompanyName: string
  issuerSignature: string
  scale: 'normal' | 'compact'
  signer: PreviewUser
}>()

const blankRowClass = computed(() =>
  props.scale === 'compact' ? 'h-[21px]' : 'h-[22px]',
)
const signatureRowClass = computed(() =>
  props.scale === 'compact' ? 'h-[26px]' : 'h-[27px]',
)
</script>

<template>
  <tr data-preview-signature>
    <td colspan="7" class="acceptance-copy align-middle">
      To indicate Customer acceptance of this quotation, please sign below and
      return one copy of this quotation to OnePro Cloud.
    </td>
  </tr>
  <tr :class="blankRowClass">
    <td colspan="7" />
  </tr>
  <tr class="font-semibold">
    <td colspan="4" />
    <td colspan="3">{{ issuerCompanyName }}</td>
  </tr>
  <tr>
    <td colspan="3" class="align-bottom" :class="signatureRowClass">
      <div class="w-[48%] border-b border-slate-900" />
    </td>
    <td />
    <td colspan="3" class="relative align-bottom" :class="signatureRowClass">
      <img
        v-if="issuerSignature"
        :src="issuerSignature"
        alt="Issuer signature"
        class="absolute bottom-1 left-0 max-h-[26px] max-w-full object-contain object-left"
      />
      <div class="w-[48%] border-b border-slate-900" />
    </td>
  </tr>
  <tr>
    <td colspan="3">Name :</td>
    <td />
    <td colspan="3">Name : {{ signer.name }}</td>
  </tr>
  <tr>
    <td colspan="3">Title :</td>
    <td />
    <td colspan="3">Title : {{ signer.title }}</td>
  </tr>
  <tr>
    <td colspan="3">Email :</td>
    <td />
    <td colspan="3" class="break-all">
      Email :
      <a :href="`mailto:${signer.email}`" class="text-inherit no-underline">
        {{ signer.email }}
      </a>
    </td>
  </tr>
</template>

<style scoped>
td {
  padding: 1px 2px;
}

td.acceptance-copy {
  height: 21px;
  padding-top: 10px;
}
</style>
