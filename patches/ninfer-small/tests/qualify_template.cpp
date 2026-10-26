#include "models/qwen3_5/frontend/tokenizer.h"
#include "models/qwen3_5/frontend/chat_template.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <filesystem>
using namespace ninfer; using namespace ninfer::models::qwen3_5::frontend;
int main(int argc,char** argv){try{
 if(argc!=3){std::cerr<<"Usage: qualify-template TEMPLATE_FILE RESOURCES_DIR\n";return 2;}
 std::ifstream f(argv[1]);std::string s((std::istreambuf_iterator<char>(f)),{});
 std::cerr<<"template begin"<<std::endl;auto t=CompiledChatTemplate::resolve(s);std::cerr<<"template loaded"<<std::endl;
 auto read=[&](const char* name){std::ifstream in(std::filesystem::path(argv[2])/name);return std::string((std::istreambuf_iterator<char>(in)),{});};
 auto tj=read("tokenizer.json"),tc=read("tokenizer_config.json"),gc=read("generation_config.json");
 std::cerr<<"tokenizer begin "<<tj.size()<<std::endl;ninfer::models::qwen3_5::frontend::Tokenizer tok({tj,tc,gc});std::cerr<<"tokenizer loaded"<<std::endl;
 for(std::string prefix:{"<think>\n\n</think>","<think>\n\n</think>\n\n<|action_start|>"}){
  ChatPart part;part.text="current game screen";ninfer::models::qwen3_5::frontend::ChatMessage u;u.parts={part};ninfer::models::qwen3_5::frontend::ChatMessage a;a.role=ChatRole::Assistant;part.text=prefix;a.parts={part};
  ChatRenderOptions opt;opt.continuation=PromptContinuationMode::ContinueFinalAssistant;opt.enable_thinking=false;
  auto r=t.render({u,a},opt);std::cout<<nlohmann::ordered_json{{"prefix",prefix},{"rendered",r.text}}<<'\n';
  auto encoded=tok.encode_with_boundaries(r.text,{}, {},r.literal_spans).input_ids;
  if(encoded!=tok.encode(r.text))throw std::runtime_error("Game protocol token ids differ from special-token encoding");
  std::cout<<nlohmann::ordered_json{{"token_ids",encoded}}<<'\n';
  if(!r.text.ends_with("<|im_start|>assistant\n"+prefix)) return 1;
 }
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 2;}
}

