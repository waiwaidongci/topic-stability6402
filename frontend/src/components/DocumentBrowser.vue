<script setup lang="ts">
import {ref,computed,watch} from 'vue';
import type {Run,Profile,RunDocument,Page} from '../types/domain';
import {researchApi} from '../api/research';
import {pct} from '../utils/format';
import Table from './common/Table.vue';
import Empty from './common/Empty.vue';
const props=defineProps<{run:Run;topics:Profile[]}>();
const page=ref(1),status=ref('all'),replicate=ref(0),reference=ref(''),data=ref<Page<RunDocument>|null>(null),error=ref(''),busy=ref(false);
const pages=computed(()=>data.value?Math.max(1,Math.ceil(data.value.total/data.value.page_size)):1);
const seeds=computed(()=>Array.from({length:props.run.config.repeats},(_,i)=>props.run.config.seed+i));
async function load(){
 if(props.run.status!=='succeeded'){data.value=null;return}
 busy.value=true;error.value='';
 try{data.value=await researchApi.runDocuments(props.run.id,status.value,reference.value.trim(),page.value,25)}
 catch(e:any){error.value=e.message;data.value=null}
 finally{busy.value=false}
}
watch([()=>props.run.id,()=>props.run.status,status,replicate,page],load,{immediate:true});
let timer:any=null;
watch(reference,()=>{clearTimeout(timer);timer=setTimeout(()=>{page.value=1;load()},350)});
function filter(s:string){status.value=s;page.value=1}
function pick(r:number){replicate.value=r;page.value=1}
</script>
<template>
<div class="section-title"><h2>逐篇激活与排除 / 按展签编号翻查</h2><small>共 {{data?.total??0}} 篇 · 第 {{page}} / {{pages}} 页 · 相对激活非后验概率</small></div>
<div class="browser-bar">
<div class="topic-tabs"><button v-for="i in run.config.repeats" :key="i" :class="{active:replicate===i-1}" @click="pick(i-1)">{{i===1?'参照':'第'+i+'次'}} · seed {{seeds[i-1]}}</button></div>
<div class="topic-tabs"><button :class="{active:status==='all'}" @click="filter('all')">全部</button><button :class="{active:status==='kept'}" @click="filter('kept')">仅有效</button><button :class="{active:status==='excluded'}" @click="filter('excluded')">仅排除</button></div>
<label class="browser-search"><input v-model="reference" placeholder="按展签编号前缀查找，如 ZC-0001"/></label>
</div>
<p v-if="error" class="notice error">{{error}}</p>
<Table v-if="data&&data.items.length" :headers="['展签 / 标题','状态',...topics.map(t=>t.label)]">
<tr v-for="d in data.items" :key="d.reference">
<td><small>{{d.reference}}</small><strong>{{d.title}}</strong></td>
<td><small v-if="d.status==='excluded'" class="excluded-reason">排除：{{d.reason}}</small><small v-else>有效</small></td>
<td v-for="t in topics" :key="t.id">{{d.relative_activations?pct(d.relative_activations[replicate]?.[t.topic_index]):'—'}}</td>
</tr>
</Table>
<Empty v-else-if="data" title="没有匹配的展签" help="调整编号前缀或状态过滤。"/>
<div class="pager" v-if="data&&data.total>0">
<button :disabled="page<=1||busy" @click="page--">← 上一页</button>
<small>第 {{page}} / {{pages}} 页 · 每页 25 篇 · {{busy?'读取中…':''}}</small>
<button :disabled="page>=pages||busy" @click="page++">下一页 →</button>
</div>
</template>
