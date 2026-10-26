// Dedicated 0.8B BF16 prompt/decode route, preserving selected-page metadata.
#include "ops/softmax_attention/dense/causal_cache/launch.h"
#include "ops/softmax_attention/dense/causal_cache/prompt_bf16.cuh"
#include "ops/kv_cache/append/launch.h"
#include "core/device.h"
#include <stdexcept>
namespace ninfer::ops::detail {
namespace {
template<class Cache,class Meta>
void small_attention(const Tensor& q,const Tensor& positions,float scale,const Cache& cache,Meta metadata,Tensor& out,cudaStream_t stream) {
 if(q.ne[1]!=8 || cache.storage!=KvCacheStorage::BFloat16) throw std::invalid_argument("GameScaling small engine: attention requires 8/2 BF16");
 using G=CausalD256H8Kv2;
 configure_cuda_device_once([&]{return cudaFuncSetAttribute(causal_attention_prompt_bf16_kernel<G,Meta>,cudaFuncAttributeMaxDynamicSharedMemorySize,kCausalPromptSmemBytes);});
 int tokens=q.ne[2];
 dim3 grid((tokens+kCausalPromptBr-1)/kCausalPromptBr,8,1);
 causal_attention_prompt_bf16_kernel<G,Meta><<<grid,kCausalPromptThreads,kCausalPromptSmemBytes,stream>>>(
 static_cast<const __nv_bfloat16*>(q.data),static_cast<const __nv_bfloat16*>(cache.k_pages.data),static_cast<const __nv_bfloat16*>(cache.v_pages.data),metadata,static_cast<const int*>(positions.data),scale,static_cast<__nv_bfloat16*>(out.data),tokens);
 CUDA_CHECK(cudaGetLastError());
}
}
bool causal_attention_prompt_fast_kernel(KvCacheStorage,bool){return false;}
void causal_attention_prompt_attention_launch(const Tensor& q,const Tensor& positions,float scale,const PagedKVLayerView& cache,Tensor& out,bool,cudaStream_t stream) {
 const PagedKVDirectMetadata metadata{static_cast<const int*>(cache.block_table.data),cache.selected_blocks!=nullptr?cache.selected_blocks:proto_selected_blocks()};
 small_attention(q,positions,scale,cache,metadata,out,stream);
}
void causal_attention_prompt_launch(const Tensor& q,const Tensor& k,const Tensor& v,const Tensor& positions,const Tensor& valid_columns,const Tensor& table_rows,float scale,PagedKVBatchLayerView cache,Tensor& out,bool,cudaStream_t stream) {
 if(q.ne[3]>1) {
  for(int b=0;b<q.ne[3];++b) {
   auto qb=q.slice(3,b,1),kb=k.slice(3,b,1),vb=v.slice(3,b,1),ob=out.slice(3,b,1);
   auto pb=positions.slice(1,b,1),rb=table_rows.slice(0,b,1);
   auto mb=valid_columns.data?valid_columns.slice(0,b,1):Tensor{};
   causal_attention_prompt_launch(qb,kb,vb,pb,mb,rb,scale,cache,ob,false,stream);
  }
  return;
 }
 kv_cache_append_batch_launch(k,v,positions,valid_columns,table_rows,cache,stream);
 const auto launch=[&]<bool Masked>(){
 const PagedKVBatchMetadata<Masked> metadata{.tables=static_cast<const int*>(cache.block_tables.data),.valid_columns=Masked?static_cast<const int*>(valid_columns.data):nullptr,.table_rows=static_cast<const int*>(table_rows.data),.table_stride=cache.block_tables.ne[0],.selected_blocks=cache.selected_blocks!=nullptr?cache.selected_blocks:proto_selected_blocks()};
 small_attention(q,positions,scale,cache,metadata,out,stream);
 };
 if(valid_columns.data==nullptr) launch.template operator()<false>();else launch.template operator()<true>();
}
}
