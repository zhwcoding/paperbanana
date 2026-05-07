> ## Documentation Index
> Fetch the complete documentation index at: https://docs.apimart.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# 通用对话接口(默认流式)

>  - 统一的对话API接口，支持所有文本生成模型
- 通过 model 参数选择不同的AI模型
- 兼容 OpenAI Chat Completions API 格式 

<RequestExample>
  ```bash cURL theme={null}

  curl --request POST \
    --url https://api.apimart.ai/v1/chat/completions \
    --header 'Authorization: Bearer <token>' \
    --header 'Content-Type: application/json' \
    --data '{
      "model": "gpt-4o", # 可替换为任意支持的模型 ID
      "messages": [
        {
          "role": "system",
          "content": "你是一个专业的AI助手。"
        },
        {
          "role": "user",
          "content": "介绍一下人工智能的发展历史。"
        }
      ]
    }'
  ```

  ```python Python theme={null}
  import requests

  url = "https://api.apimart.ai/v1/chat/completions"

  payload = {
      "model": "gpt-4o",  # 可替换为任意支持的模型 ID
      "messages": [
          {
              "role": "system",
              "content": "你是一个专业的AI助手。"
          },
          {
              "role": "user",
              "content": "介绍一下人工智能的发展历史。"
          }
      ]
  }

  headers = {
      "Authorization": "Bearer <token>",
      "Content-Type": "application/json"
  }

  response = requests.post(url, json=payload, headers=headers)

  print(response.json())
  ```

  ```javascript JavaScript theme={null}
  const url = "https://api.apimart.ai/v1/chat/completions";

  const payload = {
    model: "gpt-4o",  // 可替换为任意支持的模型 ID
    messages: [
      {
        role: "system",
        content: "你是一个专业的AI助手。"
      },
      {
        role: "user",
        content: "介绍一下人工智能的发展历史。"
      }
    ]
  };

  const headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  };

  fetch(url, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload)
  })
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Error:', error));
  ```

  ```go Go theme={null}
  package main

  import (
      "bytes"
      "encoding/json"
      "fmt"
      "io/ioutil"
      "net/http"
  )

  func main() {
      url := "https://api.apimart.ai/v1/chat/completions"

      payload := map[string]interface{}{
          "model": "gpt-4o",  // 可替换为任意支持的模型 ID
          "messages": []map[string]string{
              {
                  "role":    "system",
                  "content": "你是一个专业的AI助手。",
              },
              {
                  "role":    "user",
                  "content": "介绍一下人工智能的发展历史。",
              },
          },
      }

      jsonData, _ := json.Marshal(payload)

      req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
      req.Header.Set("Authorization", "Bearer <token>")
      req.Header.Set("Content-Type", "application/json")

      client := &http.Client{}
      resp, err := client.Do(req)
      if err != nil {
          panic(err)
      }
      defer resp.Body.Close()

      body, _ := ioutil.ReadAll(resp.Body)
      fmt.Println(string(body))
  }
  ```

  ```java Java theme={null}
  import java.net.http.HttpClient;
  import java.net.http.HttpRequest;
  import java.net.http.HttpResponse;
  import java.net.URI;

  public class Main {
      public static void main(String[] args) throws Exception {
          String url = "https://api.apimart.ai/v1/chat/completions";

          // 可替换为任意支持的模型 ID
          String payload = """
          {
            "model": "gpt-4o",
            "messages": [
              {
                "role": "system",
                "content": "你是一个专业的AI助手。"
              },
              {
                "role": "user",
                "content": "介绍一下人工智能的发展历史。"
              }
            ]
          }
          """;

          HttpClient client = HttpClient.newHttpClient();
          HttpRequest request = HttpRequest.newBuilder()
              .uri(URI.create(url))
              .header("Authorization", "Bearer <token>")
              .header("Content-Type", "application/json")
              .POST(HttpRequest.BodyPublishers.ofString(payload))
              .build();

          HttpResponse<String> response = client.send(request,
              HttpResponse.BodyHandlers.ofString());

          System.out.println(response.body());
      }
  }
  ```

  ```php PHP theme={null}
  <?php

  $url = "https://api.apimart.ai/v1/chat/completions";

  // 可替换为任意支持的模型 ID
  $payload = [
      "model" => "gpt-4o",
      "messages" => [
          [
              "role" => "system",
              "content" => "你是一个专业的AI助手。"
          ],
          [
              "role" => "user",
              "content" => "介绍一下人工智能的发展历史。"
          ]
      ]
  ];

  $ch = curl_init($url);
  curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
  curl_setopt($ch, CURLOPT_POST, true);
  curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
  curl_setopt($ch, CURLOPT_HTTPHEADER, [
      "Authorization: Bearer <token>",
      "Content-Type: application/json"
  ]);

  $response = curl_exec($ch);
  curl_close($ch);

  echo $response;
  ?>
  ```

  ```ruby Ruby theme={null}
  require 'net/http'
  require 'json'
  require 'uri'

  url = URI("https://api.apimart.ai/v1/chat/completions")

  # 可替换为任意支持的模型 ID
  payload = {
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: "你是一个专业的AI助手。"
      },
      {
        role: "user",
        content: "介绍一下人工智能的发展历史。"
      }
    ]
  }

  http = Net::HTTP.new(url.host, url.port)
  http.use_ssl = true

  request = Net::HTTP::Post.new(url)
  request["Authorization"] = "Bearer <token>"
  request["Content-Type"] = "application/json"
  request.body = payload.to_json

  response = http.request(request)
  puts response.body
  ```

  ```swift Swift theme={null}
  import Foundation

  let url = URL(string: "https://api.apimart.ai/v1/chat/completions")!

  let payload: [String: Any] = [
      "model": "gpt-4o",  // 可替换为任意支持的模型 ID
      "messages": [
          [
              "role": "system",
              "content": "你是一个专业的AI助手。"
          ],
          [
              "role": "user",
              "content": "介绍一下人工智能的发展历史。"
          ]
      ]
  ]

  var request = URLRequest(url: url)
  request.httpMethod = "POST"
  request.setValue("Bearer <token>", forHTTPHeaderField: "Authorization")
  request.setValue("application/json", forHTTPHeaderField: "Content-Type")
  request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

  let task = URLSession.shared.dataTask(with: request) { data, response, error in
      if let error = error {
          print("Error: \(error)")
          return
      }
      
      if let data = data, let responseString = String(data: data, encoding: .utf8) {
          print(responseString)
      }
  }

  task.resume()
  ```

  ```csharp C# theme={null}
  using System;
  using System.Net.Http;
  using System.Text;
  using System.Threading.Tasks;

  class Program
  {
      static async Task Main(string[] args)
      {
          var url = "https://api.apimart.ai/v1/chat/completions";

          // 可替换为任意支持的模型 ID
          var payload = @"{
              ""model"": ""gpt-4o"",
              ""messages"": [
                  {
                      ""role"": ""system"",
                      ""content"": ""你是一个专业的AI助手。""
                  },
                  {
                      ""role"": ""user"",
                      ""content"": ""介绍一下人工智能的发展历史。""
                  }
              ]
          }";

          using var client = new HttpClient();
          client.DefaultRequestHeaders.Add("Authorization", "Bearer <token>");

          var content = new StringContent(payload, Encoding.UTF8, "application/json");
          var response = await client.PostAsync(url, content);
          var result = await response.Content.ReadAsStringAsync();

          Console.WriteLine(result);
      }
  }
  ```

  ```c C theme={null}
  #include <stdio.h>
  #include <curl/curl.h>

  int main(void) {
      CURL *curl;
      CURLcode res;

      curl_global_init(CURL_GLOBAL_DEFAULT);
      curl = curl_easy_init();

      if(curl) {
          const char *url = "https://api.apimart.ai/v1/chat/completions";
          // 可替换为任意支持的模型 ID
          const char *payload = "{"
              "\"model\":\"gpt-4o\","
              "\"messages\":[{\"role\":\"system\",\"content\":\"你是一个专业的AI助手。\"},{\"role\":\"user\",\"content\":\"介绍一下人工智能的发展历史。\"}]"
          "}";

          struct curl_slist *headers = NULL;
          headers = curl_slist_append(headers, "Authorization: Bearer <token>");
          headers = curl_slist_append(headers, "Content-Type: application/json");

          curl_easy_setopt(curl, CURLOPT_URL, url);
          curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
          curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

          res = curl_easy_perform(curl);

          if(res != CURLE_OK) {
              fprintf(stderr, "curl_easy_perform() failed: %s\n",
                      curl_easy_strerror(res));
          }

          curl_slist_free_all(headers);
          curl_easy_cleanup(curl);
      }

      curl_global_cleanup();
      return 0;
  }
  ```

  ```objectivec Objective-C theme={null}
  #import <Foundation/Foundation.h>

  int main(int argc, const char * argv[]) {
      @autoreleasepool {
          NSURL *url = [NSURL URLWithString:@"https://api.apimart.ai/v1/chat/completions"];
          
          // 可替换为任意支持的模型 ID
          NSDictionary *payload = @{
              @"model": @"gpt-4o",
              @"messages": @[
                  @{
                      @"role": @"system",
                      @"content": @"你是一个专业的AI助手。"
                  },
                  @{
                      @"role": @"user",
                      @"content": @"介绍一下人工智能的发展历史。"
                  }
              ]
          };
          
          NSError *error;
          NSData *jsonData = [NSJSONSerialization dataWithJSONObject:payload
                                                            options:0
                                                              error:&error];
          
          NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
          [request setHTTPMethod:@"POST"];
          [request setValue:@"Bearer <token>" forHTTPHeaderField:@"Authorization"];
          [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
          [request setHTTPBody:jsonData];
          
          NSURLSessionDataTask *task = [[NSURLSession sharedSession] 
              dataTaskWithRequest:request
              completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
                  if (error) {
                      NSLog(@"Error: %@", error);
                      return;
                  }
                  NSString *result = [[NSString alloc] initWithData:data 
                                                          encoding:NSUTF8StringEncoding];
                  NSLog(@"%@", result);
              }];
          
          [task resume];
          [[NSRunLoop mainRunLoop] run];
      }
      return 0;
  }
  ```

  ```ocaml OCaml theme={null}
  (* Requires cohttp and yojson libraries *)
  open Lwt
  open Cohttp
  open Cohttp_lwt_unix

  let url = "https://api.apimart.ai/v1/chat/completions"

  (* 可替换为任意支持的模型 ID *)
  let payload = {|{
    "model": "gpt-4o",
    "messages": [
      {
        "role": "system",
        "content": "你是一个专业的AI助手。"
      },
      {
        "role": "user",
        "content": "介绍一下人工智能的发展历史。"
      }
    ]
  }|}

  let () =
    let headers = Header.init ()
      |> fun h -> Header.add h "Authorization" "Bearer <token>"
      |> fun h -> Header.add h "Content-Type" "application/json"
    in
    let body = Cohttp_lwt.Body.of_string payload in
    
    let response = Client.post ~headers ~body (Uri.of_string url) >>= fun (resp, body) ->
      body |> Cohttp_lwt.Body.to_string >|= fun body_str ->
      print_endline body_str
    in
    Lwt_main.run response
  ```

  ```dart Dart theme={null}
  import 'dart:convert';
  import 'package:http/http.dart' as http;

  void main() async {
    final url = Uri.parse('https://api.apimart.ai/v1/chat/completions');
    
    // 可替换为任意支持的模型 ID
    final payload = {
      'model': 'gpt-4o',
      'messages': [
        {
          'role': 'system',
          'content': '你是一个专业的AI助手。'
        },
        {
          'role': 'user',
          'content': '介绍一下人工智能的发展历史。'
        }
      ]
    };
    
    final response = await http.post(
      url,
      headers: {
        'Authorization': 'Bearer <token>',
        'Content-Type': 'application/json',
      },
      body: jsonEncode(payload),
    );
    
    print(response.body);
  }
  ```

  ```r R theme={null}
  library(httr)
  library(jsonlite)

  url <- "https://api.apimart.ai/v1/chat/completions"

  # 可替换为任意支持的模型 ID
  payload <- list(
    model = "gpt-4o",
    messages = list(
      list(
        role = "system",
        content = "你是一个专业的AI助手。"
      ),
      list(
        role = "user",
        content = "介绍一下人工智能的发展历史。"
      )
    )
  )

  response <- POST(
    url,
    add_headers(
      Authorization = "Bearer <token>",
      `Content-Type` = "application/json"
    ),
    body = toJSON(payload, auto_unbox = TRUE),
    encode = "raw"
  )

  cat(content(response, "text"))
  ```
</RequestExample>

<ResponseExample>
  ```json 200 theme={null}
  {
    "code": 200,
    "data": {
      "id": "chatcmpl-9876543210",
      "object": "chat.completion",
      "created": 1677652288,
      "model": "gpt-4o",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "人工智能（AI）的发展历史可以追溯到20世纪50年代...\n\n1. **早期阶段（1950s-1960s）**：图灵测试的提出标志着AI研究的开始...\n\n2. **专家系统时代（1970s-1980s）**：基于规则的系统开始应用于医疗诊断、金融分析等领域...\n\n3. **机器学习兴起（1990s-2000s）**：统计学习方法逐渐成为主流...\n\n4. **深度学习革命（2010s-至今）**：神经网络技术的突破带来了AI的爆发式发展..."
          },
          "finish_reason": "stop"
        }
      ],
      "usage": {
        "prompt_tokens": 28,
        "completion_tokens": 320,
        "total_tokens": 348
      }
    }
  }
  ```

  ```json 400 theme={null}
  {
    "error": {
      "code": 400,
      "message": "请求参数无效",
      "type": "invalid_request_error"
    }
  }
  ```

  ```json 401 theme={null}
  {
    "error": {
      "code": 401,
      "message": "身份验证失败，请检查您的API密钥",
      "type": "authentication_error"
    }
  }
  ```

  ```json 402 theme={null}
  {
    "error": {
      "code": 402,
      "message": "账户余额不足，请充值后再试",
      "type": "payment_required"
    }
  }
  ```

  ```json 403 theme={null}
  {
    "error": {
      "code": 403,
      "message": "访问被禁止，您没有权限访问此资源",
      "type": "permission_error"
    }
  }
  ```

  ```json 429 theme={null}
  {
    "error": {
      "code": 429,
      "message": "请求过于频繁，请稍后再试",
      "type": "rate_limit_error"
    }
  }
  ```

  ```json 500 theme={null}
  {
    "error": {
      "code": 500,
      "message": "服务器内部错误，请稍后重试",
      "type": "server_error"
    }
  }
  ```

  ```json 502 theme={null}
  {
    "error": {
      "code": 502,
      "message": "网关错误，服务器暂时不可用",
      "type": "bad_gateway"
    }
  }
  ```
</ResponseExample>

## Authorizations

<ParamField header="Authorization" type="string" required>
  所有接口均需要使用Bearer Token进行认证

  获取 API Key：

  访问 [API Key 管理页面](https://apimart.ai/keys) 获取您的 API Key

  使用时在请求头中添加：

  ```
  Authorization: Bearer YOUR_API_KEY
  ```
</ParamField>

## Body

<ParamField body="model" type="string" required default="gpt-5">
  模型名称

  支持的模型包括：

  * **OpenAI**: `gpt-5`, `gpt-5-chat-latest`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-pro`
  * **Anthropic**: `claude-sonnet-4-5-20250929`, `claude-opus-4-1-20250805`, `claude-haiku-4-5-20251001`, `claude-opus-4-1-20250805-thinking`, `claude-sonnet-4-5-20250929-thinking`
  * **Google**: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-pro-thinking`, `gemini-2.5-flash-lite`
  * **DeepSeek**: `deepseek-v3.1-250821`, `deepseek-v3.1-think-250821`, `deepseek-v3-0324`
  * **Doubao**: `doubao-seed-1-6-251015`, `doubao-seed-1-6-flash-250828`, `doubao-seed-1-6-thinking-250715`
  * 更多模型持续更新中...
</ParamField>

<ParamField body="messages" type="array" required>
  对话消息列表

  消息数组，每条消息包含 `role` 和 `content` 两个字段。

  **💡 快速填写（Try it 区域）：**

  1. 点击 "+ Add an item" 添加一条消息
  2. `role` 输入：`user`（用户消息）、`assistant`（AI回复）或 `system`（系统提示词）
  3. `content` 输入：你想说的话

  <Expandable title="详细字段说明">
    <ParamField body="role" type="string" required default="user">
      角色类型

      可选值：`user`（用户消息）、`assistant`（AI回复，用于多轮对话）、`system`（系统提示词，设置AI行为）
    </ParamField>

    <ParamField body="content" type="string" required>
      消息内容

      填写你想说的话或问题
    </ParamField>
  </Expandable>

  **示例：**

  ```json theme={null}
  [{"role": "user", "content": "你好，请介绍一下你自己"}]
  ```

  **进阶用法：**

  添加系统提示词（让 AI 扮演特定角色）：

  ```json theme={null}
  [
    {"role": "system", "content": "你是专业的Python导师"},
    {"role": "user", "content": "如何学习编程？"}
  ]
  ```

  多轮对话（包含上下文）：

  ```json theme={null}
  [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的？"},
    {"role": "user", "content": "介绍一下人工智能"}
  ]
  ```

  **角色说明：**

  * `user`: 用户消息（大多数情况用这个）
  * `system`: 系统提示词，设置 AI 的行为和角色
  * `assistant`: AI 的历史回复，用于多轮对话时提供上下文
</ParamField>

<ParamField body="temperature" type="number">
  控制输出随机性，范围 0-2

  * 较低的值（如 0.2）使输出更确定
  * 较高的值（如 1.8）使输出更随机

  默认值：1.0
</ParamField>

<ParamField body="max_tokens" type="integer">
  生成的最大token数量

  不同模型有不同的最大值限制，请参考具体模型文档
</ParamField>

<ParamField body="stream" type="boolean">
  是否使用流式输出

  * `true`: 流式返回（SSE格式）
  * `false`: 一次性返回完整响应

  默认值：true
</ParamField>

<ParamField body="top_p" type="number">
  核采样参数，范围 0-1

  控制生成文本的多样性，建议与 temperature 二选一使用

  默认值：1.0
</ParamField>

<ParamField body="frequency_penalty" type="number">
  频率惩罚，范围 -2.0 到 2.0

  正值会降低重复使用相同词汇的可能性

  默认值：0
</ParamField>

<ParamField body="presence_penalty" type="number">
  存在惩罚，范围 -2.0 到 2.0

  正值会增加谈论新主题的可能性

  默认值：0
</ParamField>

<ParamField body="stop" type="string or array">
  停止序列

  最多4个序列，遇到这些序列时将停止生成
</ParamField>

<ParamField body="n" type="integer">
  生成的回复数量

  默认值：1

  **⚠️ 注意：** 必须输入纯数字（如 `1`），不要加引号，否则会报错
</ParamField>

## Response

<ResponseField name="id" type="string">
  响应的唯一标识符
</ResponseField>

<ResponseField name="object" type="string">
  对象类型，固定为 `chat.completion`
</ResponseField>

<ResponseField name="created" type="integer">
  创建时间戳
</ResponseField>

<ResponseField name="model" type="string">
  实际使用的模型名称
</ResponseField>

<ResponseField name="choices" type="array">
  生成的回复列表

  <Expandable title="属性">
    <ResponseField name="index" type="integer">
      选项索引
    </ResponseField>

    <ResponseField name="message" type="object">
      消息内容

      <Expandable title="属性">
        <ResponseField name="role" type="string">
          角色类型（assistant）
        </ResponseField>

        <ResponseField name="content" type="string">
          生成的文本内容
        </ResponseField>
      </Expandable>
    </ResponseField>

    <ResponseField name="finish_reason" type="string">
      结束原因

      可能的值：

      * `stop` - 自然结束
      * `length` - 达到最大长度
      * `content_filter` - 内容过滤
      * `function_call` - 函数调用
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="usage" type="object">
  token使用统计

  <Expandable title="属性">
    <ResponseField name="prompt_tokens" type="integer">
      输入消息的token数
    </ResponseField>

    <ResponseField name="completion_tokens" type="integer">
      生成内容的token数
    </ResponseField>

    <ResponseField name="total_tokens" type="integer">
      总token数
    </ResponseField>
  </Expandable>
</ResponseField>

## 支持的模型列表

### OpenAI 系列

* `gpt-5` - GPT-5 基础模型
* `gpt-5-chat-latest` - GPT-5 最新对话版本
* `gpt-5-mini` - GPT-5 轻量级版本，性价比高
* `gpt-5-nano` - GPT-5 超轻量版本
* `gpt-5-pro` - GPT-5 专业增强版

### Anthropic 系列

* `claude-haiku-4-5-20251001` - Claude 4.5 快速响应版本
* `claude-sonnet-4-5-20250929` - Claude 4.5 平衡版本
* `claude-opus-4-1-20250805` - 最强大的 Claude 4.1 旗舰模型
* `claude-opus-4-1-20250805-thinking` - Claude 4.1 Opus 深度思考版
* `claude-sonnet-4-5-20250929-thinking` - Claude 4.5 Sonnet 深度思考版

### Google 系列

* `gemini-2.5-flash` - Gemini 2.5 快速版
* `gemini-2.5-pro` - Gemini 2.5 专业版
* `gemini-2.5-flash-lite` - Gemini 2.5 超轻量版
* `gemini-2.5-pro-thinking` - Gemini 2.5 Pro 深度思考版

### DeepSeek 系列

* `deepseek-v3.1-250821` - DeepSeek V3.1 基础版
* `deepseek-v3.1-think-250821` - DeepSeek V3.1 思考版
* `deepseek-v3-0324` - DeepSeek V3 标准版

### Doubao 系列

* `doubao-seed-1-6-flash-250828` - Doubao Seed 1.6 快速版
* `doubao-seed-1-6-thinking-250715` - Doubao Seed 1.6 思考版
* `doubao-seed-1-6-251015` - Doubao Seed 1.6 标准版

## 使用示例

### 基础对话

```json theme={null}
{
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "你好"}
  ]
}
```

### 系统提示词

```json theme={null}
{
  "model": "claude-3-5-sonnet",
  "messages": [
    {"role": "system", "content": "你是一位专业的Python编程导师"},
    {"role": "user", "content": "如何使用列表推导式？"}
  ]
}
```

### 多轮对话

```json theme={null}
{
  "model": "gemini-2.0-flash",
  "messages": [
    {"role": "user", "content": "什么是机器学习？"},
    {"role": "assistant", "content": "机器学习是人工智能的一个分支..."},
    {"role": "user", "content": "能举个例子吗？"}
  ]
}
```

### 流式输出

```json theme={null}
{
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "写一首关于春天的诗"}
  ],
  "stream": true
}
```


> ## Documentation Index
> Fetch the complete documentation index at: https://docs.apimart.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Gemini 原生格式

>  - 使用 Google 原生 API 格式调用 Gemini 模型
- 同步处理模式，实时返回对话内容
- 最简化参数，快速上手 

<RequestExample>
  ```bash cURL theme={null}
  curl --request POST \
    --url https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent \
    --header 'Authorization: Bearer <token>' \
    --header 'Content-Type: application/json' \
    --data '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "你好，介绍一下自己"
          }
        ]
      }
    ]
  }'
  ```

  ```python Python theme={null}
  import requests

  url = "https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent"

  payload = {
      "contents": [
          {
              "role": "user",
              "parts": [
                  {
                      "text": "你好，介绍一下自己"
                  }
              ]
          }
      ]
  }

  headers = {
      "Authorization": "Bearer <token>",
      "Content-Type": "application/json"
  }

  response = requests.post(url, json=payload, headers=headers)

  print(response.json())
  ```

  ```javascript JavaScript theme={null}
  const url = "https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent";

  const payload = {
    contents: [
      {
        role: "user",
        parts: [
          {
            text: "你好，介绍一下自己"
          }
        ]
      }
    ]
  };

  const headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
  };

  fetch(url, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload)
  })
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Error:', error));
  ```

  ```go Go theme={null}
  package main

  import (
      "bytes"
      "encoding/json"
      "fmt"
      "io/ioutil"
      "net/http"
  )

  func main() {
      url := "https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent"

      payload := map[string]interface{}{
          "contents": []map[string]interface{}{
              {
                  "role": "user",
                  "parts": []map[string]interface{}{
                      {
                          "text": "你好，介绍一下自己",
                      },
                  },
              },
          },
      }

      jsonData, _ := json.Marshal(payload)

      req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
      req.Header.Set("Authorization", "Bearer <token>")
      req.Header.Set("Content-Type", "application/json")

      client := &http.Client{}
      resp, err := client.Do(req)
      if err != nil {
          panic(err)
      }
      defer resp.Body.Close()

      body, _ := ioutil.ReadAll(resp.Body)
      fmt.Println(string(body))
  }
  ```

  ```java Java theme={null}
  import java.net.http.HttpClient;
  import java.net.http.HttpRequest;
  import java.net.http.HttpResponse;
  import java.net.URI;

  public class Main {
      public static void main(String[] args) throws Exception {
          String url = "https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent";

          String payload = """
          {
            "contents": [
              {
                "role": "user",
                "parts": [
                  {
                    "text": "你好，介绍一下自己"
                  }
                ]
              }
            ]
          }
          """;

          HttpClient client = HttpClient.newHttpClient();
          HttpRequest request = HttpRequest.newBuilder()
              .uri(URI.create(url))
              .header("Authorization", "Bearer <token>")
              .header("Content-Type", "application/json")
              .POST(HttpRequest.BodyPublishers.ofString(payload))
              .build();

          HttpResponse<String> response = client.send(request,
              HttpResponse.BodyHandlers.ofString());

          System.out.println(response.body());
      }
  }
  ```

  ```php PHP theme={null}
  <?php

  $url = "https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent";

  $payload = [
      "contents" => [
          [
              "role" => "user",
              "parts" => [
                  [
                      "text" => "你好，介绍一下自己"
                  ]
              ]
          ]
      ]
  ];

  $ch = curl_init($url);
  curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
  curl_setopt($ch, CURLOPT_POST, true);
  curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
  curl_setopt($ch, CURLOPT_HTTPHEADER, [
      "Authorization: Bearer <token>",
      "Content-Type: application/json"
  ]);

  $response = curl_exec($ch);
  curl_close($ch);

  echo $response;
  ?>
  ```

  ```ruby Ruby theme={null}
  require 'net/http'
  require 'json'
  require 'uri'

  url = URI("https://api.apimart.ai/v1beta/models/gemini-2.5-pro:generateContent")

  payload = {
    contents: [
      {
        role: "user",
        parts: [
          {
            text: "你好，介绍一下自己"
          }
        ]
      }
    ]
  }

  http = Net::HTTP.new(url.host, url.port)
  http.use_ssl = true

  request = Net::HTTP::Post.new(url)
  request["Authorization"] = "Bearer <token>"
  request["Content-Type"] = "application/json"
  request.body = payload.to_json

  response = http.request(request)
  puts response.body
  ```
</RequestExample>

<ResponseExample>
  ```json 200 theme={null}
  {
    "code": 200,
    "data": {
      "candidates": [
        {
          "content": {
            "role": "model",
            "parts": [
              {
                "text": "你好！很高兴能向你介绍我自己。\n\n我是一个大型语言模型，由 Google 训练和开发..."
              }
            ]
          },
          "finishReason": "STOP",
          "index": 0,
          "safetyRatings": [
            {
              "category": "HARM_CATEGORY_HATE_SPEECH",
              "probability": "NEGLIGIBLE"
            }
          ]
        }
      ],
      "promptFeedback": {
        "safetyRatings": [
          {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "probability": "NEGLIGIBLE"
          }
        ]
      ]
    },
    "usageMetadata": {
      "promptTokenCount": 4,
      "candidatesTokenCount": 611,
      "totalTokenCount": 2422,
      "thoughtsTokenCount": 1807,
      "promptTokensDetails": [
        {
          "modality": "TEXT",
          "tokenCount": 4
        }
      ]
    }
  }
  ```

  ```json 400 theme={null}
  {
    "error": {
      "code": 400,
      "message": "无效的请求参数",
      "status": "INVALID_ARGUMENT"
    }
  }
  ```

  ```json 401 theme={null}
  {
    "error": {
      "code": 401,
      "message": "认证失败，请检查 API Key",
      "status": "UNAUTHENTICATED"
    }
  }
  ```

  ```json 402 theme={null}
  {
    "error": {
      "code": 402,
      "message": "余额不足，请充值",
      "status": "PAYMENT_REQUIRED"
    }
  }
  ```

  ```json 403 theme={null}
  {
    "error": {
      "code": 403,
      "message": "没有访问权限",
      "status": "PERMISSION_DENIED"
    }
  }
  ```

  ```json 404 theme={null}
  {
    "error": {
      "code": 404,
      "message": "找不到指定的模型",
      "status": "NOT_FOUND"
    }
  }
  ```

  ```json 429 theme={null}
  {
    "error": {
      "code": 429,
      "message": "请求过于频繁，请稍后重试",
      "status": "RESOURCE_EXHAUSTED"
    }
  }
  ```

  ```json 500 theme={null}
  {
    "error": {
      "code": 500,
      "message": "服务器内部错误",
      "status": "INTERNAL"
    }
  }
  ```

  ```json 502 theme={null}
  {
    "error": {
      "code": 502,
      "message": "网关错误，服务暂时不可用",
      "status": "BAD_GATEWAY"
    }
  }
  ```

  ```json 503 theme={null}
  {
    "error": {
      "code": 503,
      "message": "服务暂时不可用",
      "status": "UNAVAILABLE"
    }
  }
  ```
</ResponseExample>

## Authorizations

<ParamField header="Authorization" type="string" required>
  所有接口均需要使用Bearer Token进行认证

  获取 API Key：

  访问 [API Key 管理页面](https://apimart.ai/keys) 获取您的 API Key

  使用时在请求头中添加：

  ```
  Authorization: Bearer YOUR_API_KEY
  ```
</ParamField>

## Path Parameters

<ParamField path="model" type="string" required>
  模型名称

  示例中使用 `gemini-2.5-pro`，您可以将其替换为其他支持的 Gemini 模型：

  * `gemini-2.5-flash` - Gemini 2.5 快速版
  * `gemini-2.5-pro` - Gemini 2.5 专业版
  * `gemini-2.5-flash-lite` - Gemini 2.5 超轻量版
  * `gemini-2.5-pro-thinking` - Gemini 2.5 Pro 深度思考版
</ParamField>

<ParamField path="method" type="enum<string>" required>
  生成方法（快速开始推荐使用 `generateContent`）：

  * `generateContent`: 等待完整响应后一次性返回
  * `streamGenerateContent`: 流式返回，逐块实时返回内容

  可选值：`generateContent`, `streamGenerateContent`
</ParamField>

## Body

<ParamField body="contents" type="array" required>
  对话内容列表

  最少需要1条消息

  <Expandable title="contents 对象结构">
    <ParamField body="role" type="string" required>
      角色类型：

      * `user`: 用户消息
      * `model`: 模型响应（对话历史中使用）
    </ParamField>

    <ParamField body="parts" type="array" required>
      消息内容部分

      <Expandable title="parts 对象结构">
        <ParamField body="text" type="string">
          文本内容
        </ParamField>

        <ParamField body="inlineData" type="object">
          内联数据（用于多模态输入）

          <Expandable title="inlineData 属性">
            <ParamField body="mimeType" type="string">
              MIME 类型，如 `image/jpeg`, `image/png`
            </ParamField>

            <ParamField body="data" type="string">
              Base64 编码的数据
            </ParamField>
          </Expandable>
        </ParamField>
      </Expandable>
    </ParamField>
  </Expandable>

  示例：

  ```json theme={null}
  [
    {
      "role": "user",
      "parts": [{ "text": "你好，介绍一下自己" }]
    }
  ]
  ```
</ParamField>

<ParamField body="generationConfig" type="object">
  生成配置（可选）

  <Expandable title="generationConfig 属性">
    <ParamField body="temperature" type="number">
      控制输出随机性，范围 0.0-2.0

      * 较低的值使输出更确定
      * 较高的值使输出更随机

      默认值：1.0
    </ParamField>

    <ParamField body="maxOutputTokens" type="integer">
      生成的最大 token 数量

      不同模型有不同的最大值限制
    </ParamField>

    <ParamField body="topP" type="number">
      核采样参数，范围 0.0-1.0

      控制采样时考虑的概率质量
    </ParamField>

    <ParamField body="topK" type="integer">
      Top-K 采样参数

      每步只从概率最高的 K 个 token 中采样
    </ParamField>

    <ParamField body="stopSequences" type="array">
      停止序列列表

      遇到这些序列时停止生成
    </ParamField>
  </Expandable>
</ParamField>

<ParamField body="safetySettings" type="array">
  安全设置（可选）

  <Expandable title="safetySettings 对象结构">
    <ParamField body="category" type="string">
      安全类别：

      * `HARM_CATEGORY_HATE_SPEECH`: 仇恨言论
      * `HARM_CATEGORY_DANGEROUS_CONTENT`: 危险内容
      * `HARM_CATEGORY_HARASSMENT`: 骚扰
      * `HARM_CATEGORY_SEXUALLY_EXPLICIT`: 色情内容
    </ParamField>

    <ParamField body="threshold" type="string">
      阈值级别：

      * `BLOCK_NONE`: 不阻止
      * `BLOCK_ONLY_HIGH`: 仅阻止高风险
      * `BLOCK_MEDIUM_AND_ABOVE`: 阻止中等及以上风险
      * `BLOCK_LOW_AND_ABOVE`: 阻止低等及以上风险
    </ParamField>
  </Expandable>
</ParamField>

## Response

<ResponseField name="candidates" type="array">
  候选响应列表

  <Expandable title="candidates 对象结构">
    <ResponseField name="content" type="object">
      生成的内容

      <Expandable title="content 属性">
        <ResponseField name="role" type="string">
          角色，通常为 `model`
        </ResponseField>

        <ResponseField name="parts" type="array">
          内容部分列表

          <Expandable title="parts 对象">
            <ResponseField name="text" type="string">
              生成的文本内容
            </ResponseField>
          </Expandable>
        </ResponseField>
      </Expandable>
    </ResponseField>

    <ResponseField name="finishReason" type="string">
      完成原因：

      * `STOP`: 正常结束
      * `MAX_TOKENS`: 达到最大 token 限制
      * `SAFETY`: 因安全原因停止
      * `RECITATION`: 因重复内容停止
      * `OTHER`: 其他原因
    </ResponseField>

    <ResponseField name="index" type="integer">
      候选响应的索引
    </ResponseField>

    <ResponseField name="safetyRatings" type="array">
      安全评级列表

      <Expandable title="safetyRatings 对象">
        <ResponseField name="category" type="string">
          安全类别
        </ResponseField>

        <ResponseField name="probability" type="string">
          概率级别：`NEGLIGIBLE`, `LOW`, `MEDIUM`, `HIGH`
        </ResponseField>
      </Expandable>
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="promptFeedback" type="object">
  提示词反馈信息

  <Expandable title="promptFeedback 属性">
    <ResponseField name="safetyRatings" type="array">
      提示词的安全评级
    </ResponseField>

    <ResponseField name="blockReason" type="string">
      阻止原因（如果提示词被阻止）
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="usageMetadata" type="object">
  使用量统计

  <Expandable title="usageMetadata 属性">
    <ResponseField name="promptTokenCount" type="integer">
      提示词消耗的 token 数
    </ResponseField>

    <ResponseField name="candidatesTokenCount" type="integer">
      候选响应消耗的 token 数
    </ResponseField>

    <ResponseField name="totalTokenCount" type="integer">
      总消耗 token 数
    </ResponseField>

    <ResponseField name="thoughtsTokenCount" type="integer">
      思考过程消耗的 token 数（如适用）
    </ResponseField>

    <ResponseField name="promptTokensDetails" type="array">
      提示词 token 详情

      <Expandable title="promptTokensDetails 对象">
        <ResponseField name="modality" type="string">
          模态类型：`TEXT`, `IMAGE`, 等
        </ResponseField>

        <ResponseField name="tokenCount" type="integer">
          该模态的 token 数量
        </ResponseField>
      </Expandable>
    </ResponseField>
  </Expandable>
</ResponseField>


> ## Documentation Index
> Fetch the complete documentation index at: https://docs.apimart.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# OpenAI 多模态响应接口

>  - 完全兼容 OpenAI Responses API 格式
- 支持文本和图像的多模态输入
- 支持工具扩展：网络搜索、文件搜索、函数调用、远程MCP 

<RequestExample>
  ```bash cURL theme={null}
  curl https://api.apimart.ai/v1/responses \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <token>" \
    -d '{
      "model": "gpt-5",
      "input": [
        {
          "role": "user",
          "content": [
            {
              "type": "input_text",
              "text": "这张图片里有什么？"
            },
            {
              "type": "input_image",
              "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png"
            }
          ]
        }
      ]
    }'
  ```

  ```python Python theme={null}
  import requests
  import os

  url = "https://api.apimart.ai/v1/responses"

  payload = {
      "model": "gpt-5",
      "input": [
          {
              "role": "user",
              "content": [
                  {
                      "type": "input_text",
                      "text": "这张图片里有什么？"
                  },
                  {
                      "type": "input_image",
                      "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png"
                  }
              ]
          }
      ]
  }

  headers = {
      "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}",
      "Content-Type": "application/json"
  }

  response = requests.post(url, json=payload, headers=headers)

  print(response.json())
  ```

  ```javascript JavaScript theme={null}
  const url = "https://api.apimart.ai/v1/responses";

  const payload = {
    model: "gpt-5",
    input: [
      {
        role: "user",
        content: [
          {
            type: "input_text",
            text: "这张图片里有什么？"
          },
          {
            type: "input_image",
            image_url: "https://openai-documentation.vercel.app/images/cat_and_otter.png"
          }
        ]
      }
    ]
  };

  const headers = {
    "Authorization": `Bearer ${process.env.OPENAI_API_KEY}`,
    "Content-Type": "application/json"
  };

  fetch(url, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload)
  })
    .then(response => response.json())
    .then(data => console.log(data))
    .catch(error => console.error('Error:', error));
  ```

  ```go Go theme={null}
  package main

  import (
      "bytes"
      "encoding/json"
      "fmt"
      "io/ioutil"
      "net/http"
      "os"
  )

  func main() {
      url := "https://api.apimart.ai/v1/responses"

      payload := map[string]interface{}{
          "model": "gpt-5",
          "input": []map[string]interface{}{
              {
                  "role": "user",
                  "content": []map[string]string{
                      {
                          "type": "input_text",
                          "text": "这张图片里有什么？",
                      },
                      {
                          "type":      "input_image",
                          "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png",
                      },
                  },
              },
          },
      }

      jsonData, _ := json.Marshal(payload)

      req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
      req.Header.Set("Authorization", "Bearer "+os.Getenv("OPENAI_API_KEY"))
      req.Header.Set("Content-Type", "application/json")

      client := &http.Client{}
      resp, err := client.Do(req)
      if err != nil {
          panic(err)
      }
      defer resp.Body.Close()

      body, _ := ioutil.ReadAll(resp.Body)
      fmt.Println(string(body))
  }
  ```

  ```java Java theme={null}
  import java.net.http.HttpClient;
  import java.net.http.HttpRequest;
  import java.net.http.HttpResponse;
  import java.net.URI;

  public class Main {
      public static void main(String[] args) throws Exception {
          String url = "https://api.apimart.ai/v1/responses";
          String apiKey = System.getenv("OPENAI_API_KEY");

          String payload = """
          {
            "model": "gpt-5",
            "input": [
              {
                "role": "user",
                "content": [
                  {
                    "type": "input_text",
                    "text": "这张图片里有什么？"
                  },
                  {
                    "type": "input_image",
                    "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png"
                  }
                ]
              }
            ]
          }
          """;

          HttpClient client = HttpClient.newHttpClient();
          HttpRequest request = HttpRequest.newBuilder()
              .uri(URI.create(url))
              .header("Authorization", "Bearer " + apiKey)
              .header("Content-Type", "application/json")
              .POST(HttpRequest.BodyPublishers.ofString(payload))
              .build();

          HttpResponse<String> response = client.send(request,
              HttpResponse.BodyHandlers.ofString());

          System.out.println(response.body());
      }
  }
  ```

  ```php PHP theme={null}
  <?php

  $url = "https://api.apimart.ai/v1/responses";
  $apiKey = getenv('OPENAI_API_KEY');

  $payload = [
      "model" => "gpt-5",
      "input" => [
          [
              "role" => "user",
              "content" => [
                  [
                      "type" => "input_text",
                      "text" => "这张图片里有什么？"
                  ],
                  [
                      "type" => "input_image",
                      "image_url" => "https://openai-documentation.vercel.app/images/cat_and_otter.png"
                  ]
              ]
          ]
      ]
  ];

  $ch = curl_init($url);
  curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
  curl_setopt($ch, CURLOPT_POST, true);
  curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
  curl_setopt($ch, CURLOPT_HTTPHEADER, [
      "Authorization: Bearer " . $apiKey,
      "Content-Type: application/json"
  ]);

  $response = curl_exec($ch);
  curl_close($ch);

  echo $response;
  ?>
  ```

  ```ruby Ruby theme={null}
  require 'net/http'
  require 'json'
  require 'uri'

  url = URI("https://api.apimart.ai/v1/responses")
  api_key = ENV['OPENAI_API_KEY']

  payload = {
    model: "gpt-5",
    input: [
      {
        role: "user",
        content: [
          {
            type: "input_text",
            text: "这张图片里有什么？"
          },
          {
            type: "input_image",
            image_url: "https://openai-documentation.vercel.app/images/cat_and_otter.png"
          }
        ]
      }
    ]
  }

  http = Net::HTTP.new(url.host, url.port)
  http.use_ssl = true

  request = Net::HTTP::Post.new(url)
  request["Authorization"] = "Bearer #{api_key}"
  request["Content-Type"] = "application/json"
  request.body = payload.to_json

  response = http.request(request)
  puts response.body
  ```

  ```swift Swift theme={null}
  import Foundation

  let url = URL(string: "https://api.apimart.ai/v1/responses")!
  let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] ?? ""

  let payload: [String: Any] = [
      "model": "gpt-5",
      "input": [
          [
              "role": "user",
              "content": [
                  [
                      "type": "input_text",
                      "text": "这张图片里有什么？"
                  ],
                  [
                      "type": "input_image",
                      "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png"
                  ]
              ]
          ]
      ]
  ]

  var request = URLRequest(url: url)
  request.httpMethod = "POST"
  request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
  request.setValue("application/json", forHTTPHeaderField: "Content-Type")
  request.httpBody = try? JSONSerialization.data(withJSONObject: payload)

  let task = URLSession.shared.dataTask(with: request) { data, response, error in
      if let error = error {
          print("Error: \(error)")
          return
      }
      
      if let data = data, let responseString = String(data: data, encoding: .utf8) {
          print(responseString)
      }
  }

  task.resume()
  ```

  ```csharp C# theme={null}
  using System;
  using System.Net.Http;
  using System.Text;
  using System.Threading.Tasks;

  class Program
  {
      static async Task Main(string[] args)
      {
          var url = "https://api.apimart.ai/v1/responses";
          var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");

          var payload = @"{
              ""model"": ""gpt-5"",
              ""input"": [
                  {
                      ""role"": ""user"",
                      ""content"": [
                          {
                              ""type"": ""input_text"",
                              ""text"": ""这张图片里有什么？""
                          },
                          {
                              ""type"": ""input_image"",
                              ""image_url"": ""https://openai-documentation.vercel.app/images/cat_and_otter.png""
                          }
                      ]
                  }
              ]
          }";

          using var client = new HttpClient();
          client.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");

          var content = new StringContent(payload, Encoding.UTF8, "application/json");
          var response = await client.PostAsync(url, content);
          var result = await response.Content.ReadAsStringAsync();

          Console.WriteLine(result);
      }
  }
  ```

  ```c C theme={null}
  #include <stdio.h>
  #include <curl/curl.h>
  #include <stdlib.h>

  int main(void) {
      CURL *curl;
      CURLcode res;
      const char *api_key = getenv("OPENAI_API_KEY");

      curl_global_init(CURL_GLOBAL_DEFAULT);
      curl = curl_easy_init();

      if(curl) {
          const char *url = "https://api.apimart.ai/v1/responses";
          const char *payload = "{"
              "\"model\":\"gpt-5\","
              "\"input\":[{\"role\":\"user\",\"content\":[{\"type\":\"input_text\",\"text\":\"这张图片里有什么？\"},{\"type\":\"input_image\",\"image_url\":\"https://openai-documentation.vercel.app/images/cat_and_otter.png\"}]}]"
          "}";

          char auth_header[256];
          snprintf(auth_header, sizeof(auth_header), "Authorization: Bearer %s", api_key);

          struct curl_slist *headers = NULL;
          headers = curl_slist_append(headers, auth_header);
          headers = curl_slist_append(headers, "Content-Type: application/json");

          curl_easy_setopt(curl, CURLOPT_URL, url);
          curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
          curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

          res = curl_easy_perform(curl);

          if(res != CURLE_OK) {
              fprintf(stderr, "curl_easy_perform() failed: %s\n",
                      curl_easy_strerror(res));
          }

          curl_slist_free_all(headers);
          curl_easy_cleanup(curl);
      }

      curl_global_cleanup();
      return 0;
  }
  ```

  ```objectivec Objective-C theme={null}
  #import <Foundation/Foundation.h>

  int main(int argc, const char * argv[]) {
      @autoreleasepool {
          NSURL *url = [NSURL URLWithString:@"https://api.apimart.ai/v1/responses"];
          NSString *apiKey = [NSProcessInfo processInfo].environment[@"OPENAI_API_KEY"];
          
          NSDictionary *payload = @{
              @"model": @"gpt-5",
              @"input": @[
                  @{
                      @"role": @"user",
                      @"content": @[
                          @{
                              @"type": @"input_text",
                              @"text": @"这张图片里有什么？"
                          },
                          @{
                              @"type": @"input_image",
                              @"image_url": @"https://openai-documentation.vercel.app/images/cat_and_otter.png"
                          }
                      ]
                  }
              ]
          };
          
          NSError *error;
          NSData *jsonData = [NSJSONSerialization dataWithJSONObject:payload
                                                            options:0
                                                              error:&error];
          
          NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
          [request setHTTPMethod:@"POST"];
          [request setValue:[NSString stringWithFormat:@"Bearer %@", apiKey] 
              forHTTPHeaderField:@"Authorization"];
          [request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
          [request setHTTPBody:jsonData];
          
          NSURLSessionDataTask *task = [[NSURLSession sharedSession] 
              dataTaskWithRequest:request
              completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
                  if (error) {
                      NSLog(@"Error: %@", error);
                      return;
                  }
                  NSString *result = [[NSString alloc] initWithData:data 
                                                          encoding:NSUTF8StringEncoding];
                  NSLog(@"%@", result);
              }];
          
          [task resume];
          [[NSRunLoop mainRunLoop] run];
      }
      return 0;
  }
  ```

  ```ocaml OCaml theme={null}
  (* Requires cohttp and yojson libraries *)
  open Lwt
  open Cohttp
  open Cohttp_lwt_unix

  let url = "https://api.apimart.ai/v1/responses"
  let api_key = Sys.getenv "OPENAI_API_KEY"

  let payload = {|{
    "model": "gpt-5",
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": "这张图片里有什么？"
          },
          {
            "type": "input_image",
            "image_url": "https://openai-documentation.vercel.app/images/cat_and_otter.png"
          }
        ]
      }
    ]
  }|}

  let () =
    let headers = Header.init ()
      |> fun h -> Header.add h "Authorization" ("Bearer " ^ api_key)
      |> fun h -> Header.add h "Content-Type" "application/json"
    in
    let body = Cohttp_lwt.Body.of_string payload in
    
    let response = Client.post ~headers ~body (Uri.of_string url) >>= fun (resp, body) ->
      body |> Cohttp_lwt.Body.to_string >|= fun body_str ->
      print_endline body_str
    in
    Lwt_main.run response
  ```

  ```dart Dart theme={null}
  import 'dart:convert';
  import 'dart:io';
  import 'package:http/http.dart' as http;

  void main() async {
    final url = Uri.parse('https://api.apimart.ai/v1/responses');
    final apiKey = Platform.environment['OPENAI_API_KEY'];
    
    final payload = {
      'model': 'gpt-5',
      'input': [
        {
          'role': 'user',
          'content': [
            {
              'type': 'input_text',
              'text': '这张图片里有什么？'
            },
            {
              'type': 'input_image',
              'image_url': 'https://openai-documentation.vercel.app/images/cat_and_otter.png'
            }
          ]
        }
      ]
    };
    
    final response = await http.post(
      url,
      headers: {
        'Authorization': 'Bearer $apiKey',
        'Content-Type': 'application/json',
      },
      body: jsonEncode(payload),
    );
    
    print(response.body);
  }
  ```

  ```r R theme={null}
  library(httr)
  library(jsonlite)

  url <- "https://api.apimart.ai/v1/responses"
  api_key <- Sys.getenv("OPENAI_API_KEY")

  payload <- list(
    model = "gpt-5",
    input = list(
      list(
        role = "user",
        content = list(
          list(
            type = "input_text",
            text = "这张图片里有什么？"
          ),
          list(
            type = "input_image",
            image_url = "https://openai-documentation.vercel.app/images/cat_and_otter.png"
          )
        )
      )
    )
  )

  response <- POST(
    url,
    add_headers(
      Authorization = paste("Bearer", api_key),
      `Content-Type` = "application/json"
    ),
    body = toJSON(payload, auto_unbox = TRUE),
    encode = "raw"
  )

  cat(content(response, "text"))
  ```
</RequestExample>

<ResponseExample>
  ```json 200 theme={null}
  {
    "code": 200,
    "data": {
      "id": "resp-9876543210",
      "object": "response",
      "created": 1677652288,
      "model": "gpt-5",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "这张图片中有一只猫和一只水獭。它们看起来正在互动，场景非常可爱和温馨。猫咪和水獭似乎相处得很融洽。"
          },
          "finish_reason": "stop"
        }
      ],
      "usage": {
        "prompt_tokens": 156,
        "completion_tokens": 45,
        "total_tokens": 201
      }
    }
  }
  ```

  ```json 400 theme={null}
  {
    "error": {
      "code": 400,
      "message": "请求参数无效",
      "type": "invalid_request_error"
    }
  }
  ```

  ```json 401 theme={null}
  {
    "error": {
      "code": 401,
      "message": "身份验证失败，请检查您的API密钥",
      "type": "authentication_error"
    }
  }
  ```

  ```json 402 theme={null}
  {
    "error": {
      "code": 402,
      "message": "账户余额不足，请充值后再试",
      "type": "payment_required"
    }
  }
  ```

  ```json 403 theme={null}
  {
    "error": {
      "code": 403,
      "message": "访问被禁止，您没有权限访问此资源",
      "type": "permission_error"
    }
  }
  ```

  ```json 429 theme={null}
  {
    "error": {
      "code": 429,
      "message": "请求过于频繁，请稍后再试",
      "type": "rate_limit_error"
    }
  }
  ```

  ```json 500 theme={null}
  {
    "error": {
      "code": 500,
      "message": "服务器内部错误，请稍后重试",
      "type": "server_error"
    }
  }
  ```

  ```json 502 theme={null}
  {
    "error": {
      "code": 502,
      "message": "网关错误，服务器暂时不可用",
      "type": "bad_gateway"
    }
  }
  ```
</ResponseExample>

## Authorizations

<ParamField header="Authorization" type="string" required>
  所有接口均需要使用Bearer Token进行认证

  获取 API Key：

  访问 [API Key 管理页面](https://apimart.ai/keys) 获取您的 API Key

  使用时在请求头中添加：

  ```
  Authorization: Bearer YOUR_API_KEY
  ```
</ParamField>

## Body

<ParamField body="model" type="string" required default="gpt-5">
  模型名称

  支持的模型包括：

  * `gpt-5` - OpenAI 最新多模态模型
  * `GPT-4o-image` - GPT-4 优化版多模态模型
  * `gpt-4-vision` - GPT-4 视觉理解模型
  * 更多模型持续更新中...
</ParamField>

<ParamField body="input" type="array" required>
  输入内容列表

  输入数组，每个输入项包含 `role` 和 `content` 两个字段。

  **💡 快速填写（Try it 区域）：**

  1. 点击 "+ Add an item" 添加一个输入项
  2. `role` 输入：`user`（用户消息）、`assistant`（AI回复）或 `system`（系统提示词）
  3. `content` 添加内容块（可包含文本和图像）

  <Expandable title="详细字段说明">
    <ParamField body="role" type="string" required default="user">
      角色类型

      可选值：`user`（用户消息）、`assistant`（AI回复，用于多轮对话）、`system`（系统提示词，设置AI行为）
    </ParamField>

    <ParamField body="content" type="array" required>
      内容数组

      支持多种类型的内容块，可以包含文本和图像。

      <Expandable title="内容块类型">
        <ParamField body="type" type="string" required>
          内容类型

          可选值：

          * `input_text`: 文本输入
          * `input_image`: 图像输入
        </ParamField>

        <ParamField body="text" type="string">
          文本内容

          当 `type` 为 `input_text` 时使用，填写文本内容
        </ParamField>

        <ParamField body="image_url" type="string">
          图像URL

          当 `type` 为 `input_image` 时使用

          支持两种格式：

          **1. 完整的图像URL地址**

          * 公开可访问的图像URL（http\:// 或 https\://）
          * 示例：`https://example.com/image.jpg`

          **2. Base64 编码格式**

          * **必须使用完整的 Data URI 格式**
          * 格式：`data:image/{格式};base64,{base64数据}`
          * 支持的图片格式：jpeg、png、gif、webp
          * 示例：`data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABg...`
          * ⚠️ 注意：必须包含 `data:image/jpeg;base64,` 前缀部分
        </ParamField>
      </Expandable>
    </ParamField>
  </Expandable>
</ParamField>

<ParamField body="temperature" type="number">
  控制输出随机性，范围 0-2

  * 较低的值（如 0.2）使输出更确定
  * 较高的值（如 1.8）使输出更随机

  默认值：1.0
</ParamField>

<ParamField body="max_tokens" type="integer">
  生成的最大token数量

  不同模型有不同的最大值限制，请参考具体模型文档
</ParamField>

<ParamField body="stream" type="boolean">
  是否使用流式输出

  * `true`: 流式返回（SSE格式）
  * `false`: 一次性返回完整响应

  默认值：false
</ParamField>

<ParamField body="top_p" type="number">
  核采样参数，范围 0-1

  控制生成文本的多样性，建议与 temperature 二选一使用

  默认值：1.0
</ParamField>

<ParamField body="tools" type="array">
  工具列表，用于扩展模型能力

  支持的工具类型：

  * **网络搜索** (`web_search`): 实时搜索互联网信息
  * **文件搜索** (`file_search`): 搜索已上传的文件内容
  * **函数调用** (`function`): 调用自定义函数
  * **远程MCP** (`remote_mcp`): 连接远程模型上下文协议服务

  示例：`[{"type": "web_search"}]`
</ParamField>

## Response

<ResponseField name="id" type="string">
  响应的唯一标识符
</ResponseField>

<ResponseField name="object" type="string">
  对象类型，固定为 `response`
</ResponseField>

<ResponseField name="created" type="integer">
  创建时间戳
</ResponseField>

<ResponseField name="model" type="string">
  实际使用的模型名称
</ResponseField>

<ResponseField name="choices" type="array">
  生成的回复列表

  <Expandable title="属性">
    <ResponseField name="index" type="integer">
      选项索引
    </ResponseField>

    <ResponseField name="message" type="object">
      消息内容

      <Expandable title="属性">
        <ResponseField name="role" type="string">
          角色类型（assistant）
        </ResponseField>

        <ResponseField name="content" type="string">
          生成的文本内容
        </ResponseField>
      </Expandable>
    </ResponseField>

    <ResponseField name="finish_reason" type="string">
      结束原因

      可能的值：

      * `stop` - 自然结束
      * `length` - 达到最大长度
      * `content_filter` - 内容过滤
    </ResponseField>
  </Expandable>
</ResponseField>

<ResponseField name="usage" type="object">
  token使用统计

  <Expandable title="属性">
    <ResponseField name="prompt_tokens" type="integer">
      输入内容的token数
    </ResponseField>

    <ResponseField name="completion_tokens" type="integer">
      生成内容的token数
    </ResponseField>

    <ResponseField name="total_tokens" type="integer">
      总token数
    </ResponseField>
  </Expandable>
</ResponseField>

## 使用示例

### 纯文本输入

```json theme={null}
{
  "model": "gpt-5",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "你好，介绍一下人工智能"
        }
      ]
    }
  ]
}
```

### 使用网络搜索工具

```json theme={null}
{
  "model": "gpt-5",
  "tools": [{"type": "web_search"}],
  "input": "今天有什么正面的新闻？"
}
```

```bash cURL示例 theme={null}
curl "https://api.apimart.ai/v1/responses" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <token>" \
    -d '{
        "model": "gpt-5",
        "tools": [{"type": "web_search"}],
        "input": "今天有什么正面的新闻？"
    }'
```

### 图像理解

```json theme={null}
{
  "model": "gpt-5",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "描述这张图片"
        },
        {
          "type": "input_image",
          "image_url": "https://example.com/image.jpg"
        }
      ]
    }
  ]
}
```

### 多图像分析

```json theme={null}
{
  "model": "gpt-5",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "比较这两张图片的异同"
        },
        {
          "type": "input_image",
          "image_url": "https://example.com/image1.jpg"
        },
        {
          "type": "input_image",
          "image_url": "https://example.com/image2.jpg"
        }
      ]
    }
  ]
}
```

### Base64编码图像

```json theme={null}
{
  "model": "gpt-5",
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "分析这张图片"
        },
        {
          "type": "input_image",
          "image_url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
        }
      ]
    }
  ]
}
```

### 使用文件搜索工具

```json theme={null}
{
  "model": "gpt-5",
  "tools": [{"type": "file_search"}],
  "input": "根据已上传的文档，总结公司的季度业绩"
}
```

### 使用函数调用

```json theme={null}
{
  "model": "gpt-5",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "获取指定城市的天气信息",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {
              "type": "string",
              "description": "城市名称，例如：北京"
            },
            "unit": {
              "type": "string",
              "enum": ["celsius", "fahrenheit"],
              "description": "温度单位"
            }
          },
          "required": ["city"]
        }
      }
    }
  ],
  "input": "北京今天天气怎么样？"
}
```

### 使用远程MCP

```json theme={null}
{
  "model": "gpt-5",
  "tools": [
    {
      "type": "remote_mcp",
      "remote_mcp": {
        "url": "https://mcp.example.com/api",
        "auth_token": "your_mcp_token"
      }
    }
  ],
  "input": "查询数据库中的用户信息"
}
```

### 组合使用多个工具

```json theme={null}
{
  "model": "gpt-5",
  "tools": [
    {"type": "web_search"},
    {"type": "file_search"},
    {
      "type": "function",
      "function": {
        "name": "calculate",
        "description": "执行数学计算",
        "parameters": {
          "type": "object",
          "properties": {
            "expression": {
              "type": "string",
              "description": "数学表达式"
            }
          },
          "required": ["expression"]
        }
      }
    }
  ],
  "input": "搜索最新的比特币价格，并计算100个比特币的总价值"
}
```

## 内容类型说明

### input\_text

文本输入类型

**属性：**

* `type`: 固定为 `"input_text"`
* `text`: 文本内容（字符串）

### input\_image

图像输入类型

**属性：**

* `type`: 固定为 `"input_image"`
* `image_url`: 图像URL或Base64编码的数据URI

**支持两种格式：**

1. **完整的图像URL地址**
   * 公开可访问的图像URL（http\:// 或 https\://）
   * 示例：`https://example.com/image.jpg`

2. **Base64 编码格式**
   * **必须使用完整的 Data URI 格式**
   * 格式：`data:image/{格式};base64,{base64数据}`
   * 示例：`data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABg...`
   * ⚠️ 注意：必须包含 `data:image/jpeg;base64,` 前缀部分（其中 `jpeg` 可以替换为 `png`、`gif`、`webp` 等）

**支持的图像格式：**

* JPEG
* PNG
* GIF
* WebP

**图像大小限制：**

* 最大文件大小：20MB
* 推荐分辨率：不超过2048x2048像素

## 工具使用详解

### 网络搜索 (Web Search)

使用网络搜索工具可以让模型访问实时互联网信息。

**配置示例：**

```json theme={null}
{
  "tools": [{"type": "web_search"}]
}
```

**适用场景：**

* 查询最新新闻和时事
* 获取实时数据（股票、天气、汇率等）
* 搜索最新的技术文档和资料
* 验证事实信息

### 文件搜索 (File Search)

文件搜索工具允许模型在已上传的文档中搜索相关信息。

**配置示例：**

```json theme={null}
{
  "tools": [{"type": "file_search"}]
}
```

**适用场景：**

* 分析企业内部文档
* 搜索技术规范和手册
* 查询合同和法律文件
* 知识库问答系统

### 函数调用 (Function Calling)

定义自定义函数，让模型能够调用外部API或执行特定操作。

**完整配置示例：**

```json theme={null}
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_stock_price",
        "description": "获取股票的实时价格",
        "parameters": {
          "type": "object",
          "properties": {
            "symbol": {
              "type": "string",
              "description": "股票代码，例如：AAPL"
            },
            "currency": {
              "type": "string",
              "enum": ["USD", "CNY"],
              "description": "货币单位",
              "default": "USD"
            }
          },
          "required": ["symbol"]
        }
      }
    }
  ]
}
```

**参数说明：**

* `name`: 函数名称（必需）
* `description`: 函数功能描述（必需）
* `parameters`: 参数定义，使用JSON Schema格式
  * `type`: 参数类型
  * `properties`: 参数属性定义
  * `required`: 必需参数列表

**适用场景：**

* 调用第三方API
* 执行数据库查询
* 触发业务流程
* 与内部系统集成

### 远程MCP (Remote MCP)

连接到远程模型上下文协议（MCP）服务，扩展模型能力。

**配置示例：**

```json theme={null}
{
  "tools": [
    {
      "type": "remote_mcp",
      "remote_mcp": {
        "url": "https://your-mcp-server.com/api",
        "auth_token": "your_auth_token",
        "timeout": 30
      }
    }
  ]
}
```

**参数说明：**

* `url`: MCP服务器地址（必需）
* `auth_token`: 认证令牌（可选）
* `timeout`: 超时时间（秒），默认30秒

**适用场景：**

* 连接企业级AI服务
* 使用专业领域模型
* 访问受保护的数据源
* 分布式AI系统集成

## 工具响应格式

当模型使用工具时，响应格式会包含工具调用信息：

```json theme={null}
{
  "id": "resp-123456",
  "object": "response",
  "created": 1677652288,
  "model": "gpt-5",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "get_weather",
              "arguments": "{\"city\": \"北京\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

**工具调用流程：**

1. 模型接收用户输入
2. 分析是否需要使用工具
3. 如需要，返回工具调用请求
4. 客户端执行工具调用
5. 将工具结果返回给模型
6. 模型生成最终响应

## 注意事项

1. **图像URL要求**：
   * 必须是公开可访问的URL
   * 或使用Base64编码的Data URI格式

2. **Token计费**：
   * 图像会根据其分辨率消耗相应的tokens
   * 高分辨率图像会自动调整大小以优化成本
   * 工具调用也会消耗额外的tokens

3. **内容顺序**：
   * content数组中的元素顺序会影响模型理解
   * 建议先放置文本指令，再放置图像

4. **多模态组合**：
   * 可以在一个请求中混合多个文本和图像
   * 支持多轮对话，保持上下文连贯性

5. **工具使用限制**：
   * 同时使用多个工具时，模型会智能选择最合适的工具
   * 函数调用需要明确的函数定义和参数说明
   * 网络搜索结果可能受地域和时间限制

6. **API兼容性**：
   * 完全兼容OpenAI Responses API格式
   * 可无缝迁移现有OpenAI代码
   * 支持所有OpenAI工具扩展功能


Gemini API - Google Gemini 模型 | APIMart
Apimart
API 市场
OpenClaw
API 文档
API 更新
博客
GitHub

$0.97
LLM
Gemini
Google Gemini 模型系列——从极速 Flash 到强大的 Pro，拥有超大上下文窗口和原生多模态理解能力。

多模态
长上下文
思维
服务亮点
99.9% SLA
官方折扣
按量计费
高速低延
gemini-3.1-pro-preview
gemini-3-flash-preview-nothinking
gemini-3-pro-preview
gemini-3-pro-preview-thinking
gemini-3-flash-preview
gemini-2.5-pro-thinking
gemini-2.5-pro-nothinking
gemini-2.5-flash-thinking
gemini-2.5-flash-nothinking
gemini-2.5-pro
gemini-2.5-flash-lite
gemini-2.5-flash
gemini-2.0-flash
Input
gemini-3-flash-preview

Advanced Settings
Start a conversation

Type a message below to begin

Say something...
定价详情
透明定价，无隐藏费用。按量付费，用多少付多少。

型号	输入	输出
gemini-3.1-pro-preview	$1.6/M	$9.6/M
gemini-3-flash-preview-nothinking	$0.4/M	$2.4/M
gemini-3-pro-preview	$1.6/M	$9.6/M
gemini-3-pro-preview-thinking	$1.6/M	$9.6/M
gemini-3-flash-preview	$0.4/M	$2.4/M
gemini-2.5-pro-thinking	$1/M	$8/M
gemini-2.5-pro-nothinking	$1/M	$8/M
gemini-2.5-flash-thinking	$0.24/M	$1.99992/M
gemini-2.5-flash-nothinking	$0.24/M	$1.99992/M
gemini-2.5-pro	$1/M	$8/M
gemini-2.5-flash-lite	$0.08/M	$0.32/M
gemini-2.5-flash	$0.24/M	$1.99992/M
gemini-2.0-flash	$0.08/M	$0.32/M
* 实际费用以最终输出为准。

Gemini API - Google 语言模型
访问完整的 Gemini 系列，从 Flash Lite 到 Gemini 3 Pro。业界领先的百万级上下文窗口、原生多模态能力和高级思维模式。

50K+

活跃用户

99.9%

在线率

2x

更快

70%

成本节省

Gemini API 核心功能
Gemini 成为多模态 AI 首选的理由

超大上下文
处理超过 100 万 token——在单次请求中分析整本书、完整代码库或数小时的对话。

原生多模态
Gemini 在单一模型中原生理解文本、图像、音频和视频。

思维模式
思维变体使用扩展推理来解决复杂的数学、编程和科学问题。

Flash 极速
Gemini Flash 和 Flash Lite 为延迟敏感型应用提供超快响应。

深度搜索
Gemini DeepSearch 模型将推理与网络搜索相结合，提供全面的研究答案。

广泛语言支持
在 40 多种语言中表现出色，适用于全球化应用。

信息溯源与事实性
通过 Google 搜索集成将回答建立在真实数据之上，减少幻觉并提高事实准确性。

代码执行
在模型中执行 Python 代码进行计算、数据分析和生成图表——实现精确、可验证的结果。

Gemini API 使用场景
团队如何在生产环境中使用 Gemini 模型

大型文档分析
利用百万级上下文，在单次 API 调用中处理整本书、法律文件或研究论文。

视觉理解
分析图像、图表、示意图和视频帧，用于内容审核、数据提取等。

AI 研究助手
使用 DeepSearch 进行带引用来源和多步推理的深度研究。

大规模对话
部署 Flash Lite，实现高性价比、高吞吐量的大规模对话 AI。

代码生成
利用 Gemini Pro 强大的编程能力生成和审查代码。

教育与辅导
构建能理解文本、图像和示意图的多模态辅导系统。

开始使用 Gemini API
几分钟内开始使用 Google 模型

1
注册并充值
创建免费的 APIMart 账户并充值余额。

→
2
获取 API Key
生成 API Key 以编程方式访问 Gemini 模型。

→
3
开始构建
使用上方的在线体验，或通过兼容 OpenAI 的 API 进行集成。

用户评价
开发者对我们 Gemini API 的评价

“百万级上下文窗口是颠覆性的。我们的代码审查工具可以在一次调用中处理整个代码库。”

Alex Chen

工程负责人

“Gemini Flash 速度极快且价格低廉，非常适合我们的实时翻译服务。”

Sarah Li

产品经理

“多模态能力让我们可以用单一流水线处理文本、图像和文档。”

Mike Wang

机器学习工程师

“Gemini 2.5 Pro Thinking 是我们处理复杂分析任务的首选，推理质量非常出色。”

Emily Zhou

数据科学家

“DeepSearch 对我们的研究产品来说太棒了，它能自动查找并引用来源。”

David Liu

高级开发者

“我们用 Flash Lite 做大批量摘要生成，相比 GPT-4 节省了大量成本。”

Lisa Zhang

平台工程师

常见问题
关于使用 Gemini API 的常见问题

提供哪些 Gemini 模型？
什么是思维模型？
如何计费？
API 是否兼容 OpenAI SDK？
我的数据安全吗？
应该选择哪个 Gemini 模型？
相关模型
探索同类型的其他模型。

查看全部模型 →
OpenAI
GPT-4o Mini


gpt-4o-mini is a lightweight multimodal model released by OpenAI.

IN
$0.12/M
$0.15/M
OUT
$0.48/M
$0.6/M
省 20%
Vertex
gemini-2.0-flash


Gemini 2.0 Flash is an artificial intelligence model provided by google-vertex.

IN
$0.08/M
$0.1/M
OUT
$0.32/M
$0.4/M
省 20%
Zhipu
glm-5.1


GLM-5.1 is Zhipu's flagship AI model, excelling in programming, complex reasoning, and long-chain tasks, making it particularly well-suited for agent-based and automation development scenarios.

IN
$0.8/M
$1/M
OUT
$1.44/M
$1.8/M
省 20%
OpenAI
gpt-5-mini


GPT-5-Mini is a lightweight version of the GPT-5 model released by OpenAI.

IN
$0.2/M
$0.25/M
OUT
$1.6/M
$2/M
省 20%
Apimart
官方 AI API 聚合，计价透明，一站管理密钥与用量


Toggle theme
模型

Seedream 5.0 Lite API
Seedream 4.5 API
Sora 2 API
Sora 2 Pro API
Veo 3.1 API
Nano Banana API
Seedream 4 API
Nano Banana Pro API
Nano Banana 2 API
GPT-4o Image API
所有模型
替代方案

Fal.ai 替代方案
Wavespeed AI 替代方案
PiAPI 替代方案
CometAPI 替代方案
Replicate 替代方案
AIMLAPI 替代方案
EachLabs 替代方案
资源

API 文档
隐私政策
服务条款
Cookie 政策
网站地图
© 2026 APIMart. 保留所有权利。