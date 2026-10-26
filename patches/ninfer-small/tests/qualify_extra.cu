#include "ninfer/ops/causal_conv1d_silu.h"
#include "ninfer/ops/rope.h"
#include "ninfer/ops/attn_input_proj.h"
#include "ninfer/ops/gdn_input_proj.h"
#include "ninfer/ops/gdn_gating_proj.h"
#include "ninfer/ops/linear_add.h"
#include "ninfer/ops/linear.h"
#include "ninfer/ops/linear_swiglu.h"
#include "ninfer/ops/rmsnorm.h"
#include "ninfer/ops/softmax_attention.h"
#include "core/device.h"

#include <cuda_bf16.h>

#include <algorithm>
#include <cmath>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ninfer;

namespace {
std::mt19937 rng(5070);
std::normal_distribution<float> normal(0.0f, 0.4f);

double value(__nv_bfloat16 x) { return __bfloat162float(x); }

std::vector<__nv_bfloat16> random_values(std::size_t count) {
    std::vector<__nv_bfloat16> result(count);
    for (auto& x : result) x = __float2bfloat16_rn(normal(rng));
    return result;
}

void upload(DeviceBuffer& buffer, const auto& values) {
    buffer.copy_from_host(values.data(), values.size() * sizeof(values[0]));
}

// Criteria belong to the mathematical Op; every reported output must be finite.
struct Error {
    double squared_error = 0.0;
    double squared_reference = 0.0;
    double maximum_error = 0.0;
    double maximum_reference = 0.0;
    std::size_t count = 0;
    bool finite = true;

    void add(double actual, double expected) {
        finite = finite && std::isfinite(actual) && std::isfinite(expected);
        const double difference = actual - expected;
        squared_error += difference * difference;
        squared_reference += expected * expected;
        maximum_error = std::max(maximum_error, std::abs(difference));
        maximum_reference = std::max(maximum_reference, std::abs(expected));
        ++count;
    }

    bool report(const std::string& name, bool swiglu = false) const {
        const double rms = std::sqrt(squared_reference / count);
        const double nrms = std::sqrt(squared_error / squared_reference);
        const double peak = maximum_error / rms;
        // Existing LinearSwiGLU A16 criterion from tests/ops/linear_swiglu:
        // relative L2 <= 3.3e-3, gross error <= 5e-3 + 6.3e-3 * max(abs(reference)).
        const bool pass = finite && std::isfinite(nrms) && (swiglu
            ? nrms <= 0.0033 && maximum_error <= 0.005 + 0.0063 * maximum_reference
            : nrms < 0.006 && peak < 0.045);
        std::cout << "{\"case\":\"" << name << "\",\"nrms\":" << nrms
                  << ",\"max_error_over_reference_rms\":" << peak
                  << ",\"criterion\":\"" << (swiglu ? "SwiGLU A16" : "projection/attention A16") << "\""
                  << ",\"pass\":" << (pass ? "true" : "false") << "}\n" << std::flush;
        return pass;
    }
};


bool conv(int T,bool alias){
 const int C=6144;auto x=random_values(C*T),w=random_values(C*4),st=random_values(C*3);
 DeviceBuffer xb(C*T*2),wb(C*4*2),sb(C*3*2),ob(C*3*2),a(2048*T*2),b(a.bytes),c(a.bytes);
 upload(xb,x);upload(wb,w);upload(sb,st);
 Tensor tx(xb.p,DType::BF16,{C,T}),tw(wb.p,DType::BF16,{C,4}),si(sb.p,DType::BF16,{C,3}),so(alias?sb.p:ob.p,DType::BF16,{C,3});
 Tensor oa(a.p,DType::BF16,{2048,T}),ob1(b.p,DType::BF16,{2048,T}),oc(c.p,DType::BF16,{2048,T});
 ops::causal_conv1d_silu_split(tx,tw,si,so,oa,ob1,oc,nullptr);CUDA_CHECK(cudaDeviceSynchronize());
 std::vector<__nv_bfloat16> av(2048*T),bv(av.size()),cv(av.size()),sv(C*3);
 a.copy_to_host(av.data(),a.bytes);b.copy_to_host(bv.data(),b.bytes);c.copy_to_host(cv.data(),c.bytes);(alias?sb:ob).copy_to_host(sv.data(),sv.size()*2);
 auto u=[&](int ch,int t){return t<0?value(st[(t+3)*C+ch]):value(x[t*C+ch]);};Error e;bool exact=true;
 for(int ch=0;ch<C;++ch){for(int t=0;t<T;++t){double z=0;for(int j=0;j<4;++j)z+=value(w[j*C+ch])*u(ch,t-3+j);auto &v=ch<2048?av:ch<4096?bv:cv;e.add(value(v[t*2048+ch%2048]),z/(1+std::exp(-z)));}for(int j=0;j<3;++j)exact=exact&&(value(sv[j*C+ch])==u(ch,T-3+j));}
 bool pass=e.report("conv6144_T"+std::to_string(T)+(alias?"_alias":"_disjoint"));std::cout<<"{\"conv_state_exact\":"<<(exact?"true":"false")<<"}\n";return pass&&exact;
}
bool rope64(int T){
 const int D=64,H=12;auto x=random_values(D*H*T);std::vector<int> pos(T*2);for(int t=0;t<T;++t){pos[t]=t/23;pos[T+t]=t%23;}
 DeviceBuffer xb(x.size()*2),pb(pos.size()*4);upload(xb,x);upload(pb,pos);Tensor tx(xb.p,DType::BF16,{D,H,T}),tp(pb.p,DType::I32,{T,2});
 ops::rope(tp,64,10000.f,tx,nullptr);CUDA_CHECK(cudaDeviceSynchronize());std::vector<__nv_bfloat16> actual(x.size());xb.copy_to_host(actual.data(),xb.bytes);Error e;
 for(int t=0;t<T;++t)for(int h=0;h<H;++h)for(int j=0;j<32;++j){int base=(t*H+h)*D;double angle=pos[(j/16)*T+t]*std::pow(10000.,-double(j%16)/16.);double a=value(x[base+j]),b=value(x[base+j+32]);e.add(value(actual[base+j]),a*std::cos(angle)-b*std::sin(angle));e.add(value(actual[base+j+32]),b*std::cos(angle)+a*std::sin(angle));}
 return e.report("rope64_T"+std::to_string(T));
}
}
int main(){try{bool pass=true;for(int t:{1,9,128})for(bool alias:{false,true})pass=conv(t,alias)&&pass;for(int t:{1,197,1024})pass=rope64(t)&&pass;return pass?0:1;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
