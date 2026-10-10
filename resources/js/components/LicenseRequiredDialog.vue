<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { KeyRound } from 'lucide-vue-next';
import { useLicenseStore } from '@/stores/license';
import Modal from '@/components/ui/Modal.vue';
import Button from '@/components/ui/Button.vue';

const license = useLicenseStore();
const router = useRouter();
const open = ref(false);
const message = ref('');

function onRequired(e: Event) {
    message.value = (e as CustomEvent<string>).detail || 'A licence is required to continue.';
    license.markRequired(message.value);
    open.value = true;
}
function goLicense() { open.value = false; void router.push('/license'); }
onMounted(() => window.addEventListener('hvsr-license-required', onRequired));
onBeforeUnmount(() => window.removeEventListener('hvsr-license-required', onRequired));
</script>

<template>
    <Modal :open="open" title="Licence required" @close="open = false">
        <div class="flex items-start gap-3">
            <span class="grid place-items-center size-10 rounded-xl bg-bad-500/12 text-bad-500 shrink-0"><KeyRound class="size-5" /></span>
            <div class="text-[13px]">
                <p>{{ message }}</p>
                <p class="text-muted mt-2">Your projects, recordings and results stay fully accessible. Import a licence file on the License page or request one from QuakeLogic with your Machine ID.</p>
            </div>
        </div>
        <div class="mt-5 flex justify-end gap-2">
            <Button @click="open = false">Close</Button>
            <Button variant="primary" @click="goLicense"><KeyRound class="size-4" /> Open License page</Button>
        </div>
    </Modal>
</template>
