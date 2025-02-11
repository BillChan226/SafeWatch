import torch
import transformers
import json
import sys, os

from utility.models.VidLLM.videollama import *
from utility.models.VidLLM.videollama import load_pretrained_model as load_pretrained_model_videollama
from utility.models.VidLLM.videollama import conv_templates as conv_templates_videollama
from utility.models.VLLM.frame_based import *

from utility.models.VidLLM.internvl2 import *
from utility.models.VidLLM.chatunivi import *
from utility.models.VidLLM.chatunivi import _get_rawvideo_dec
from utility.models.VidLLM.chatunivi import load_pretrained_model as load_pretrained_model_chatunivi
from utility.models.VidLLM.chatunivi import conv_templates as conv_templates_chatunivi
# from utility.models.VidLLM.HolmesVAD.demo.utils import *


from tqdm import tqdm
import time
import os
import moviepy.editor as mp
import base64
import requests
sys.path.append("/scratch/czr/Video_moderation/utility/models/VLLM/LlavaGuard/sglang/python")
import sglang as sgl
from sglang import RuntimeEndpoint
from torchtnt.utils.flops import FlopTensorDispatchMode
import torchvision.models as models
import copy
import torch.nn.functional as nnf


@sgl.function
def guard_gen(s, image_path, prompt):
    s += sgl.user(sgl.image(image_path) + prompt)
    hyperparameters = {
        'temperature': 0.5,
        'top_p': 0.95,
        'top_k': 50,
        'max_tokens': 1028,
    }
    s += sgl.assistant(sgl.gen("json_output", **hyperparameters))

def split_model(model_name):
    device_map = {}
    world_size = torch.cuda.device_count()
    num_layers = {'InternVL2-8B': 32, 'InternVL2-26B': 48,
                  'InternVL2-40B': 60, 'InternVL2-Llama3-76B': 80}[model_name]
    # Since the first GPU will be used for ViT, treat it as half a GPU.
    num_layers_per_gpu = math.ceil(num_layers / (world_size - 0.5))
    num_layers_per_gpu = [num_layers_per_gpu] * world_size
    num_layers_per_gpu[0] = math.ceil(num_layers_per_gpu[0] * 0.5)
    layer_cnt = 0
    for i, num_layer in enumerate(num_layers_per_gpu):
        for j in range(num_layer):
            device_map[f'language_model.model.layers.{layer_cnt}'] = i
            layer_cnt += 1
    device_map['vision_model'] = 0
    device_map['mlp1'] = 0
    device_map['language_model.model.tok_embeddings'] = 0
    device_map['language_model.model.embed_tokens'] = 0
    device_map['language_model.output'] = 0
    device_map['language_model.model.norm'] = 0
    device_map['language_model.lm_head'] = 0
    device_map[f'language_model.model.layers.{num_layers - 1}'] = 0

    return device_map

def extract_moderation_result_v1(model_response):
    # keys = [
    #     "C1(Sexual Content)", "C2(Harassment & Bullying)", "C3(Threats, Violence & Harm)",
    #     "C4(False & Deceptive Information)", "C5(Illegal/Regulated Activities)", "C6(Hateful Content & Extremism)"
    # ]
    keys = [
        "C1(Threats, Violence & Harm)", "C2(Sexual Content)", "C3(Harassment & Bullying)", "C4(Illegal/Regulated Activities)", "C5(Hateful Content & Extremism)", "C6(False & Deceptive Information)"
    ]
    result = {}
    for key in keys:
        # Adjust the pattern to match the entire key format
        pattern = rf'"{re.escape(key)}":\s*(true|false|True|False)'
        match = re.search(pattern, model_response)
        if match:
            value = match.group(1).lower() == 'true'
            short_key = key.split('(')[0]  # Extract the short key (e.g., C1, C2)
            result[short_key] = value
    return result

class VideoModerator:
    def __init__(self, model_id, device, ckpt_dir=None):
        self.model_id = model_id
        self.device = device
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.model_path = None
        self.model_name = None
        overwrite_path = ckpt_dir
    
        if "VideoLLaMA" in self.model_id:
            
            # 1. Initialize the model.
            # model_path = '/scratch/czr/hf_models/VideoLLaMA2-7B'
            model_path = '/scratch/czr/hf_models/VideoLLaMA2-7B-16F'
            if overwrite_path is not None:
                model_path = overwrite_path
            # Base model inference (only need to replace model_path)
            model_name = get_model_name_from_path(model_path)
            self.tokenizer, self.model, self.processor, self.context_len = load_pretrained_model_videollama(model_path, None, model_name)
            self.model = self.model.to(device)
            self.conv_mode = 'llama_2'
        
        elif "HolmesVAD" in self.model_id:
            
            model_path = "/scratch/czr/hf_models/HolmesVAD-7B"
            if overwrite_path is not None:
                model_path = overwrite_path
            self.chat = HolmesVADChat(model_path, "llama_2", device=self.device)
            self.conv_mode = "llava_v1"

        elif "InternVL2" in self.model_id:
            
            model_path = f'/scratch/czr/hf_models/{self.model_id}'
            # If you have an 80G A100 GPU, you can put the entire model on a single GPU.
            if overwrite_path is not None:
                model_path = overwrite_path
            try:
                device_map = split_model(self.model_id)
                print(device_map)

                self.model = AutoModel.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16,
                    # load_in_8bit=True,
                    low_cpu_mem_usage=True,
                    trust_remote_code=True,
                    device_map=device_map,
                    ).eval()#.to(device)
            
            except Exception as e:
                self.model = AutoModel.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16,
                    # load_in_8bit=True,
                    low_cpu_mem_usage=True,
                    trust_remote_code=True,
                    ).eval().to(device)

            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            # set the max number of tiles in `max_num`
            # policy_start_token = self.tokenizer('<box>')
            # policy_end_token = self.tokenizer('</box>')
            # print(policy_start_token, policy_end_token)
            # input()
            self.generation_config = dict(
                num_beams=1,
                max_new_tokens=256,
                # do_sample=True,
                # temperature=0.5,
                do_sample=False,
                return_dict_in_generate=True,
                output_logits=True,
            )
        
        elif "Chat-UniVi" in self.model_id:
            import os
            model_path = "/scratch/czr/hf_models/Chat-UniVi-13B"
            if overwrite_path is not None:
                model_path = overwrite_path
            # The number of visual tokens varies with the length of the video. "max_frames" is the maximum number of frames.
            # When the video is long, we will uniformly downsample the video to meet the frames when equal to the "max_frames".
            self.max_frames = 100

            # The number of frames retained per second in the video.
            self.video_framerate = 1

            # Sampling Parameter
            self.conv_mode = "guardrail"
            self.temperature = 0.2
            self.top_p = None
            self.num_beams = 1

            disable_torch_init()
            model_path = os.path.expanduser(model_path)
            model_name = "ChatUniVi"
            self.tokenizer, self.model, self.image_processor, self.context_len = load_pretrained_model_chatunivi(model_path, None, model_name)

            mm_use_im_start_end = getattr(self.model.config, "mm_use_im_start_end", False)
            mm_use_im_patch_token = getattr(self.model.config, "mm_use_im_patch_token", True)
            if mm_use_im_patch_token:
                tokenizer.add_tokens([DEFAULT_IMAGE_PATCH_TOKEN], special_tokens=True)
            if mm_use_im_start_end:
                tokenizer.add_tokens([DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN], special_tokens=True)
            self.model.resize_token_embeddings(len(self.tokenizer))

            vision_tower = self.model.get_vision_tower()
            if not vision_tower.is_loaded:
                vision_tower.load_model()
            self.image_processor = vision_tower.image_processor

            # if self.model.config.config["use_cluster"]:
            #     for n, m in self.model.named_modules():
            #         m = m.to(dtype=torch.bfloat16)

        elif "MiniCPM" in model_id:
            # Load the model and tokenizer
            model_path = "/scratch/czr/hf_models/MiniCPM-Llama3-V-2_5"
            if overwrite_path is not None:
                model_path = overwrite_path
            self.model = AutoModel.from_pretrained(model_path, trust_remote_code=True)#, torch_dtype=torch.float16)
            self.model = self.model.to(device='cuda')
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            self.model.eval()
        elif "llava-v1.6-mistral" in model_id:
            if overwrite_path is not None:
                model_path = overwrite_path
            self.processor = LlavaNextProcessor.from_pretrained("llava-hf/llava-v1.6-mistral-7b-hf")
            self.model = LlavaNextForConditionalGeneration.from_pretrained(model_path, torch_dtype=torch.float16) 
            self.model.to("cuda")
        elif "gpt-4o" in model_id:
            from openai import OpenAI
            self.client = OpenAI(api_key=OPENAI_API_KEY)

        elif "o1" in model_id:
            from openai import OpenAI
            import os
            self.api_key = os.getenv('OPENAI_API_KEY')
            self.model_id = "o1-redteam-sys"        
        elif "gemini" in model_id:
            import os
            os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
            import time
            import google.generativeai as genai
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
            self.genai = genai

            self.genai.configure(api_key=os.environ["GEMINI_API_KEY"])

            generation_config = {
            "temperature": 0.4,
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
            }

            self.model = self.genai.GenerativeModel(
            model_name = "gemini-1.5-flash",
            generation_config=generation_config,
            safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT : HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )

        elif "cambrian" in model_id:
            self.conv_mode = "llama_3"
            model_path = f'/scratch/czr/hf_models/{model_id}'
            if overwrite_path is not None:
                model_path = overwrite_path
            self.model_name = get_model_name_from_path(model_path)
            self.tokenizer, self.model, self.image_processor, self.context_len = load_pretrained_model(model_path, None, self.model_name)
            self.temperature = 0

        elif "Llama-Guard-3-11B-Vision" in model_id:
            self.model_id = model_id
            model_path = "/scratch/czr/hf_models/Llama-Guard-3-11B-Vision"
            self.processor = AutoProcessor.from_pretrained(model_path)
            self.model = AutoModelForVision2Seq.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            )
            # self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        elif "LlavaGuard" in model_id:
            backend = RuntimeEndpoint(f"http://localhost:30005")
            sgl.set_default_backend(backend)

        elif "azure" in model_id:
            self.model_id = model_id

            self.api_key = AZURE_API_KEY
            self.endpoint = "https://safewatch.cognitiveservices.azure.com/"
            self.url = f"{self.endpoint}/contentsafety/image:analyze?api-version=2023-10-01"

            # Set up the headers for the API call
            self.headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/json"
            }



    def generate_response(self, question, video_path):
        if "VideoLLaMA" in self.model_id:
            tensor = process_video(video_path, self.processor, self.model.config.image_aspect_ratio, sample_scheme='uniform').to(dtype=torch.float16, device=self.device, non_blocking=True)
            default_mm_token = DEFAULT_MMODAL_TOKEN["VIDEO"]
            modal_token_index = MMODAL_TOKEN_INDEX["VIDEO"]
            tensor = [tensor]

            # 3. text preprocess (tag process & generate prompt).
            question = default_mm_token + "\n" + question
            conv = conv_templates_videollama[self.conv_mode].copy()
            conv.append_message(conv.roles[0], question)
            conv.append_message(conv.roles[1], None)
            prompt = conv.get_prompt()
            input_ids = tokenizer_MMODAL_token(prompt, self.tokenizer, modal_token_index, return_tensors='pt').unsqueeze(0).to(self.device)

            with torch.inference_mode():
                output_ids = self.model.generate(
                    input_ids,
                    images_or_videos=tensor,
                    modal_list=['video'],
                    do_sample=True,
                    temperature=0.2,
                    max_new_tokens=1024,
                    use_cache=True,
                )

            outputs = self.tokenizer.batch_decode(output_ids, skip_special_tokens=True)
            
            return outputs[0], 0

        elif "InternVL2" in self.model_id:

            if video_path == None:
                question = question
                response, history, true_prob = self.model.chat(self.tokenizer, None, question, self.generation_config,
                                            history=None, return_history=True)
            else:
                pixel_values, num_patches_list = load_video(video_path, num_segments=8, max_num=1)
                pixel_values = pixel_values.to(self.device)
                # pixel_values = pixel_values.to(torch.bfloat16).cuda()
                video_prefix = ''.join([f'Frame{i+1}: <image>\n' for i in range(len(num_patches_list))])
                question = video_prefix + question
                # Frame1: <image>\nFrame2: <image>\n...\nFrame31: <image>\n{question}
                response, history, true_prob = self.model.chat(self.tokenizer, pixel_values, question, self.generation_config,
                                            num_patches_list=num_patches_list,
                                            history=None, return_history=True)
            return response, true_prob
                    
        elif "Chat-UniVi" in self.model_id:

            video_frames, slice_len = _get_rawvideo_dec(video_path, self.image_processor, max_frames=self.max_frames, video_framerate=self.video_framerate)
            qs = question
            cur_prompt = qs
            if self.model.config.mm_use_im_start_end:
                qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN * slice_len + DEFAULT_IM_END_TOKEN + '\n' + qs
            else:
                qs = DEFAULT_IMAGE_TOKEN * slice_len + '\n' + qs

            conv = conv_templates_chatunivi[self.conv_mode].copy()
            conv.append_message(conv.roles[0], qs)
            conv.append_message(conv.roles[1], None)
            prompt = conv.get_prompt()

            input_ids = tokenizer_image_token(prompt, self.tokenizer, IMAGE_TOKEN_INDEX, return_tensors='pt').unsqueeze(
                0).cuda()

            stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
            keywords = [stop_str]
            stopping_criteria = KeywordsStoppingCriteria(keywords, self.tokenizer, input_ids)

            with torch.inference_mode():
                output_ids = self.model.generate(
                    input_ids,
                    images=video_frames.half().cuda(),
                    do_sample=True,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    num_beams=self.num_beams,
                    output_scores=True,
                    return_dict_in_generate=True,
                    max_new_tokens=1024,
                    use_cache=True,
                    stopping_criteria=[stopping_criteria])

            output_ids = output_ids.sequences
            input_token_len = input_ids.shape[1]
            n_diff_input_output = (input_ids != output_ids[:, :input_token_len]).sum().item()
            if n_diff_input_output > 0:
                print(f'[Warning] {n_diff_input_output} output_ids are not the same as the input_ids')
            outputs = self.tokenizer.batch_decode(output_ids[:, input_token_len:], skip_special_tokens=True)[0]
            outputs = outputs.strip()
            if outputs.endswith(stop_str):
                outputs = outputs[:-len(stop_str)]
            outputs = outputs.strip()

            return outputs, 0

        elif "MiniCPM" in self.model_id:
            frame, _ = extract_single_frame(video_path)
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')

            msgs = [{'role': 'user', 'content': question}]
            
            res = self.model.chat(
                image=image,
                msgs=msgs,
                tokenizer=self.tokenizer,
                sampling=True,
                temperature=0.7,
            )
            
            generated_text = ""
            for new_text in res:
                generated_text += new_text

            return generated_text, 0

        elif "llava-v1.6-mistral-7b-hf" in self.model_id:
            frame, _ = extract_single_frame(video_path)
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')

            prompt_template = "[INST] <image>\n{prompt} [/INST]"
            question = prompt_template.format(prompt=question)

            inputs = self.processor(question, image, return_tensors="pt").to(self.device)
            outputs = self.model.generate(**inputs, max_new_tokens=1280, do_sample=True, temperature=0.7)
            generated_text = self.processor.decode(outputs[0], skip_special_tokens=True)

            generated_text = generated_text.split("[/INST]")[1].strip()

            return generated_text
        
        elif "gpt-4o" in self.model_id:

            image_size = 768
            max_new_tokens = 576
            sample_frequency = 50

            video = cv2.VideoCapture(video_path)

            # Read the video frame by frame and convert it to base64
            base64Frames = []
            while video.isOpened():
                success, frame = video.read()
                if not success:
                    break
                _, buffer = cv2.imencode(".jpg", frame)
                base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

            video.release()

            sampled_frames = base64Frames[0::sample_frequency]
            max_frame_num = 10
            if len(sampled_frames) > max_frame_num:
                # uniform sampling 20
                sampled_frames = [sampled_frames[i] for i in range(0, len(sampled_frames), len(sampled_frames)//max_frame_num)]
            
            print(len(sampled_frames), "frames read.")

            # Sample the frame from the video, every sample_frequency frames
            video_slice = map(lambda x: {"image": x, "resize": image_size}, sampled_frames)

            # Input the prompt and the video slice to the API
            PROMPT_MESSAGES = [
                {
                    "role": "user",
                    "content": [
                        question,
                        *video_slice,
                    ],
                },
            ]
            
            # print("question", question)
            # input()
            # Call the API
            params = {
                "model": "gpt-4o",
                # "model": "gpt-4o-2024-05-13",
                "messages": PROMPT_MESSAGES,
                "max_tokens": max_new_tokens,
            }
            result = self.client.chat.completions.create(**params)
            generated_text = result.choices[0].message.content

            if "yes" in generated_text.lower() or "unsafe" in generated_text.lower():
                true_prob = 1
            else:
                true_prob = 0

            return generated_text, true_prob

        elif "o1" in self.model_id:

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # Initialize content list with text
            content = [{"type": "text", "text": question}]

            image_size = 768
            sample_frequency = 50
            max_new_tokens = 576
            max_frame_num = 10

            video = cv2.VideoCapture(video_path)
            base64Frames = []

            # Read and encode video frames
            while video.isOpened():
                success, frame = video.read()
                if not success:
                    break
                _, buffer = cv2.imencode(".jpg", frame)
                base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

            video.release()

            # Sample every 'sample_frequency' frames and limit to 'max_frame_num'
            sampled_frames = base64Frames[0::sample_frequency]
            if len(sampled_frames) > max_frame_num:
                sampled_frames = [sampled_frames[i] for i in range(0, len(sampled_frames), len(sampled_frames) // max_frame_num)]

            # Append each frame to the content
            video_slice = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame}"}} for frame in sampled_frames]
            content.extend(video_slice)

            # Prepare the payload for the API request
            payload = {
                "model": self.model_id,
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ],
                # "max_tokens": max_new_tokens  # Default max tokens for response
            }

            # API call
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            # responses = [resp['message']['content'] for resp in response.json().get('choices', [])]

            # Check for specific keywords in response
            responses = [resp['message']['content'] for resp in response.json()['choices']]
            generated_text = responses[0]
            true_prob = 1

            return generated_text, true_prob


    
        elif "gemini" in self.model_id:

            def upload_to_gemini(path, mime_type=None):
                """Uploads the given file to Gemini.

                See https://ai.google.dev/gemini-api/docs/prompting_with_media
                """
                file = self.genai.upload_file(path, mime_type=mime_type)
                print(f"Uploaded file '{file.display_name}' as: {file.uri}")
                return file

            def wait_for_files_active(files):
                """Waits for the given files to be active.

                Some files uploaded to the Gemini API need to be processed before they can be
                used as prompt inputs. The status can be seen by querying the file's "state"
                field.

                This implementation uses a simple blocking polling loop. Production code
                should probably employ a more sophisticated approach.
                """
                print("Waiting for file processing...")
                for name in (file.name for file in files):
                    file = self.genai.get_file(name)
                    while file.state.name == "PROCESSING":
                        print(".", end="", flush=True)
                        time.sleep(10)
                        file = self.genai.get_file(name)
                    if file.state.name != "ACTIVE":
                        raise Exception(f"File {file.name} failed to process")
                print("...all files ready")
                print()

            files = [
                upload_to_gemini(video_path, mime_type="video/mp4"),
            ]
            
            # Some files have a processing delay. Wait for them to be ready.
            wait_for_files_active(files)
            
            contents = [
                files[0],
                question,
            ]
            
            response = self.model.generate_content(contents)

            if "yes" in response.text.lower() or "unsafe" in response.text.lower():
                true_prob = 1
            else:
                true_prob = 0

            return response.text, true_prob

        elif "cambrian" in self.model_id:
            frame, _ = extract_single_frame(video_path)
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')
            input_ids, image_tensor, image_sizes, prompt = process(image, question, self.tokenizer, self.image_processor, self.model.config, self.conv_mode)
            input_ids = input_ids.to(device=self.device, non_blocking=True)
            with torch.inference_mode():
                output_ids = self.model.generate(
                    input_ids,
                    images=image_tensor,
                    image_sizes=image_sizes,
                    do_sample=True if self.temperature > 0 else False,
                    temperature=self.temperature,
                    num_beams=1,
                    max_new_tokens=1024,
                    use_cache=True)

            generated_text = self.tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0].strip()

            return generated_text, 0
        
        elif "Llama-Guard-3-11B-Vision" == self.model_id:

            conversation = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Describe the video"
                        },
                        {
                            "type": "image",
                        },
                    ],
                }
            ]
            # image = PIL_Image.open("/scratch/czr/Video_moderation/genai_img/images/_BYeo-GbOcIbU4n9.jpg").convert("RGB")

            frame, _ = extract_single_frame(video_path)
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')
            
            input_prompt = self.processor.apply_chat_template(
                conversation,
                return_tensors="pt",
                categories = {
                    "S1": "Sexual Content",
                    "S2": "Harassment & Bullying",
                    "S3": "Threats, Violence & Harm",
                    "S4": "False & Deceptive Information",
                    "S5": "Illegal/Regulated Activities",
                    "S6": "Hateful Content & Extremism",
                },
            )

            # input_prompt = f"""
            # <|begin_of_text|><|start_header_id|>user<|end_header_id|>

            # <|image|> {question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
            # """

            # print(input_prompt)
            # input()
            
            inputs = self.processor(text=input_prompt, images=image, return_tensors="pt").to(self.model.device)
            
            prompt_len = len(inputs['input_ids'][0])
            # with FlopTensorDispatchMode(self.model) as ftdm:
            output = self.model.generate(
                        **inputs,
                        max_new_tokens=256,
                        pad_token_id=0,
                        return_dict_in_generate=True,
                        output_logits=True,
                    )

            true_token_lower = 39257
            # logits = softmax(output.logits[0][0])
            logits = nn.functional.softmax(output.logits[1][0], dim=-1)
            true_logit_lower = logits[true_token_lower]
            # print("true_logit_lower", true_logit_lower)
            # input()

            generated_tokens = output.sequences[:, prompt_len:]
            # print(input_prompt)
            response = self.processor.decode(generated_tokens[0])
            
            print(response)
            moderation_result = {
                "C1(Sexual Content)": False,
                "C2(Harassment & Bullying)": False,
                "C3(Threats, Violence & Harm)": False,
                "C4(False & Deceptive Information)": False,
                "C5(Illegal/Regulated Activities)": False,
                "C6(Hateful Content & Extremism)": False,
            }

            if "S1" in response:
                moderation_result["C1(Sexual Content)"] = True
            if "S2" in response:
                moderation_result["C2(Harassment & Bullying)"] = True
            if "S3" in response:
                moderation_result["C3(Threats, Violence & Harm)"] = True
            if "S4" in response:
                moderation_result["C4(False & Deceptive Information)"] = True
            if "S5" in response:
                moderation_result["C5(Illegal/Regulated Activities)"] = True
            if "S6" in response:
                moderation_result["C6(Hateful Content & Extremism)"] = True

            
            response = f"""
            DESCRIPTION: NA
            GUARDRAIL: {json.dumps(final_moderation_result)}
            EXPLANATION: NA
            """

            return response, true_logit_lower

        elif "Llama-Guard-3-11B-Vision-Video" == self.model_id:

            conversation = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Describe the video"
                        },
                        {
                            "type": "image",
                        },
                    ],
                }
            ]

            # Extract frames from the video and limit to the first 8 frames for efficiency
            frames, _ = extract_frames(video_path, frequency=2)
            frames = frames[:8]

            print(len(frames), "frames read.")

            # Initialize moderation result to False for all categories
            final_moderation_result = {
                "C1(Sexual Content)": False,
                "C2(Harassment & Bullying)": False,
                "C3(Threats, Violence & Harm)": False,
                "C4(False & Deceptive Information)": False,
                "C5(Illegal/Regulated Activities)": False,
                "C6(Hateful Content & Extremism)": False,
            }

            # final_moderation_result = {
            #     "C1(Threats, Violence & Harm)": False,
            #     "C2(Sexual Content)": False,
            #     "C3(Harassment & Bullying)": False,
            #     "C4(Illegal/Regulated Activities)": False,
            #     "C5(Hateful Content & Extremism)": False,
            #     "C6(False & Deceptive Information)": False,
            # }

            max_logit_value = -float('inf')  # Initialize with a very low value

            # Process each frame individually and check for flagged content
            for frame in frames:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')

                input_prompt = self.processor.apply_chat_template(
                    conversation,
                    return_tensors="pt",
                    categories = {
                        "S1": "Sexual Content",
                        "S2": "Harassment & Bullying",
                        "S3": "Threats, Violence & Harm",
                        "S4": "False & Deceptive Information",
                        "S5": "Illegal/Regulated Activities",
                        "S6": "Hateful Content & Extremism",
                    },
                )

                inputs = self.processor(text=input_prompt, images=image, return_tensors="pt").to(self.model.device)

                prompt_len = len(inputs['input_ids'][0])
                output = self.model.generate(
                            **inputs,
                            max_new_tokens=256,
                            pad_token_id=0,
                            return_dict_in_generate=True,
                            output_logits=True,
                        )

                # Get the logits and generated response
                logits = nn.functional.softmax(output.logits[1][0], dim=-1)
                generated_tokens = output.sequences[:, prompt_len:]
                response = self.processor.decode(generated_tokens[0])
                
                # Track the maximum logit value for the 'true_token_lower'
                true_token_logit = logits[39257]
                if true_token_logit > max_logit_value:
                    max_logit_value = true_token_logit

                # Check the response for flagged categories and update the final result
                if "S1" in response:
                    final_moderation_result["C1(Sexual Content)"] = True
                if "S2" in response:
                    final_moderation_result["C2(Harassment & Bullying)"] = True
                if "S3" in response:
                    final_moderation_result["C3(Threats, Violence & Harm)"] = True
                if "S4" in response:
                    final_moderation_result["C4(False & Deceptive Information)"] = True
                if "S5" in response:
                    final_moderation_result["C5(Illegal/Regulated Activities)"] = True
                if "S6" in response:
                    final_moderation_result["C6(Hateful Content & Extremism)"] = True

                # if "S1" in response:
                #     final_moderation_result["C2(Sexual Content)"] = True
                # if "S2" in response:
                #     final_moderation_result["C3(Harassment & Bullying)"] = True
                # if "S3" in response:
                #     final_moderation_result["C1(Threats, Violence & Harm)"] = True
                # if "S4" in response:
                #     final_moderation_result["C6(False & Deceptive Information)"] = True
                # if "S5" in response:
                #     final_moderation_result["C4(Illegal/Regulated Activities)"] = True
                # if "S6" in response:
                #     final_moderation_result["C5(Hateful Content & Extremism)"] = True

                # # If any frame is flagged, stop processing further (optional)
                # if any(final_moderation_result.values()):
                #     break

            # Prepare the final response
            response = f"""
            DESCRIPTION: NA
            GUARDRAIL: {json.dumps(final_moderation_result)}
            EXPLANATION: NA
            """

            return response, max_logit_value  # return the maximum logit value

        elif "Llama-Guard-3-11B-Vision-Binary" == self.model_id:

            conversation = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Describe the video"
                        },
                        {
                            "type": "image",
                        },
                    ],
                }
            ]

            # Extract frames from the video and limit to the first 8 frames for efficiency
            frames, _ = extract_frames(video_path, frequency=2)
            frames = frames[:8]

            print(len(frames), "frames read.")

            max_logit_value = -float('inf')  # Initialize with a very low value
            unsafe_token_id = 39257  # Assuming this is the token ID for "unsafe"
            final_response = "safe"  # Initialize response as safe

            # Process each frame individually and check for flagged content
            for frame in frames:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')

                # Generate input prompt with the current conversation context
                input_prompt = self.processor.apply_chat_template(
                    conversation,
                    return_tensors="pt",
                    categories = {
                        "S1": "Sexual Content",
                        "S2": "Harassment & Bullying",
                        "S3": "Threats, Violence & Harm",
                        "S4": "False & Deceptive Information",
                        "S5": "Illegal/Regulated Activities",
                        "S6": "Hateful Content & Extremism",
                    },
                )

                inputs = self.processor(text=input_prompt, images=image, return_tensors="pt").to(self.model.device)

                # Generate output and retrieve logits
                prompt_len = len(inputs['input_ids'][0])
                output = self.model.generate(
                            **inputs,
                            max_new_tokens=256,
                            pad_token_id=0,
                            return_dict_in_generate=True,
                            output_logits=True,
                        )

                # print(output.sequences[:, prompt_len:])
                

                # Softmax the logits for the 'true' token (assumed to be 'unsafe')
                logits = nnf.softmax(output.logits[1][0], dim=-1)
                true_token_logit = logits[unsafe_token_id]

                # Track the maximum logit value for the 'unsafe' token
                if true_token_logit > max_logit_value:
                    max_logit_value = true_token_logit

                # Decode the generated response
                generated_tokens = output.sequences[:, prompt_len:]
                response = self.processor.decode(generated_tokens[0])
                # print(response)
                # input()

                # If "unsafe" appears in the response, set final response as unsafe
                if "unsafe" in response.lower():
                    final_response = "unsafe"

            # Return the final response and max unsafe logit
            return final_response, max_logit_value

        elif "HolmesVAD" in self.model_id:
            images_tensor = []
            tensor = self.chat.video_processor(video_path, return_tensors='pt')['pixel_values'][0]
            tensor = tensor.to(self.device, dtype=torch.float16)
            images_tensor.append(tensor)

            # 3. text preprocess (tag process & generate prompt).
            prompt = DEFAULT_IMAGE_TOKEN + "\n" + question
            state = conv_templates[self.conv_mode].copy()
            state_ = conv_templates[self.conv_mode].copy()

            response, true_prob = self.chat.generate(images_tensor, prompt, first_run=True, state=state_)
            
            return response, true_prob

        elif "LlavaGuard" == self.model_id:
            backend = RuntimeEndpoint(f"http://localhost:30005")
            sgl.set_default_backend(backend)
            frame, _ = extract_single_frame(video_path)
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')
            # save image to temporary path
            im_path = "temp_image.jpg"  # or use another suitable path
            image.save(im_path)
            
            out = guard_gen.run(image_path=im_path, prompt=question)
            # print(out)
            response = out['json_output']

            return response, 1


        elif "LlavaGuard-Video" == self.model_id:
            backend = RuntimeEndpoint(f"http://localhost:30005")
            sgl.set_default_backend(backend)
            
            # Extract multiple frames from the video
            frames, _ = extract_frames(video_path, frequency=2)
            frames = frames[:8]  # Limit to 8 frames for efficiency

            final_moderation_result = {
                "C1": False,
                "C2": False,
                "C3": False,
                "C4": False,
                "C5": False,
                "C6": False,
            }

            for frame in frames:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')
                
                # Save the image to a temporary path
                im_path = "temp_image.jpg"  # or use another suitable path
                image.save(im_path)

                # Process the frame through the guard_gen
                out = guard_gen.run(image_path=im_path, prompt=question)
                model_response = out['json_output']

                # Extract moderation results from the response
                moderation_result = extract_moderation_result_v1(model_response)

                # Aggregate the results: If any frame is flagged, the final result should be flagged
                for key in final_moderation_result:
                    if moderation_result.get(key, False):
                        final_moderation_result[key] = True


            # Prepare the response format
            response = f"""
            VIDEO_CONTENT: NA
            VIOLATE_REASON: NA
            {json.dumps(final_moderation_result, indent=2)}
            """

            # Return the final aggregated moderation result and a placeholder logit value
            return response, 1  # Logit value is set to 1 for now

        elif "LlavaGuard-Binary" == self.model_id:
            backend = RuntimeEndpoint(f"http://localhost:30005")
            sgl.set_default_backend(backend)
            
            # Extract multiple frames from the video
            frames, _ = extract_frames(video_path, frequency=2)
            frames = frames[:8]  # Limit to 8 frames for efficiency

            for frame in frames:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')
                
                # Save the image to a temporary path
                im_path = "temp_image.jpg"  # or use another suitable path
                image.save(im_path)

                # Process the frame through the guard_gen
                out = guard_gen.run(image_path=im_path, prompt=question)
                model_response = out['json_output']

                if "unsafe" in model_response.lower():
                    return "unsafe", 1

            # Return the final aggregated moderation result and a placeholder logit value
            return "safe", 0  # Logit value is set to 1 for now            


        elif "azure" in self.model_id:
            # Path to save the converted GIF
            gif_path = "output_video.gif"

            clip = mp.VideoFileClip(video_path)

            # (Optional) Trim the video to the first 5 seconds and reduce frame rate to reduce GIF size
            clip = clip.subclip(0, 5)  # Convert only the first 5 seconds
            clip = clip.set_fps(0.5)  # Reduce frame rate to 10 FPS

            # Convert and save the video as a GIF
            clip.write_gif(gif_path)
            # print(f"GIF saved as {gif_path}")

            # Step 2: Ensure the GIF is within the 4 MB size limit
            gif_size = os.path.getsize(gif_path)
            if gif_size <= 4 * 1024 * 1024:  # Check if GIF size is <= 4 MB

                # Read the GIF file and encode it to base64
                with open(gif_path, "rb") as gif_file:
                    gif_base64 = base64.b64encode(gif_file.read()).decode('utf-8')

                # Step 3: Prepare the JSON payload with the base64-encoded GIF
                payload = {
                    "image": {
                        "content": gif_base64  # Base64 encoded GIF
                    },
                    "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],  # Categories to analyze
                    "outputType": "FourSeverityLevels"  # Output severity in four levels
                }

                # Step 4: Send the GIF to the Azure AI Content Safety API
                response = requests.post(self.url, headers=self.headers, data=json.dumps(payload))

                # Step 5: Check and print the response
                if response.status_code == 200:
                    moderation_result_response = response.json()
                    # print("Moderation result:", json.dumps(moderation_result, indent=2))
                else:
                    print(f"Error: {response.status_code} - {response.text}")

                print(moderation_result_response)
                # Initialize the custom moderation result format
                moderation_result = {
                    "C1(Sexual Content)": False,
                    "C2(Harassment & Bullying)": False,
                    "C3(Threats, Violence & Harm)": False,
                    "C4(False & Deceptive Information)": False,
                    "C5(Illegal/Regulated Activities)": False,
                    "C6(Hateful Content & Extremism)": False
                }

                # Map the categories and severity to your custom categories
                for category_analysis in moderation_result_response["categoriesAnalysis"]:
                    category = category_analysis["category"]
                    severity = category_analysis["severity"]

                    # Check the severity and map to custom categories
                    if category == "Sexual" and severity > 0:
                        moderation_result["C1(Sexual Content)"] = True
                    if category == "Violence" and severity > 0 and severity <= 4:
                        moderation_result["C2(Harassment & Bullying)"] = True
                    if category == "Violence" and severity > 4:
                        moderation_result["C3(Threats, Violence & Harm)"] = True
                    if category == "SelfHarm" and severity > 0:
                        moderation_result["C6(Hateful Content & Extremism)"] = True
                    if category == "Hate" and severity > 0:
                        moderation_result["C6(Hateful Content & Extremism)"] = True

                # Prepare the response format
                response = f"""
                VIDEO_CONTENT: NA
                VIOLATE_REASON: NA
                {json.dumps(moderation_result, indent=2)}
                """

                return response, 1

            else:
                # raise error print(f"The GIF size exceeds the 4 MB limit (Actual size: {gif_size / 1024 / 1024:.2f} MB). Please reduce the video size or frame rate.")
                # raise Exception(f"The GIF size exceeds the 4 MB limit (Actual size: {gif_size / 1024 / 1024:.2f} MB). Please reduce the video size or frame rate.")
                frame, _ = extract_single_frame(video_path)
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGB')
                image_path = "temp_image_azure.jpg"
                image.save(image_path)

                with open(image_path, "rb") as image_file:
                    image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

                # Prepare the JSON payload with the base64-encoded image
                payload = {
                    "image": {
                        "content": image_base64  # Base64 encoded image
                    },
                    "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],  # Categories to analyze
                    "outputType": "FourSeverityLevels"  # Output severity in four levels
                }

                # Send the image to the Azure AI Content Safety API
                response = requests.post(self.url, headers=self.headers, data=json.dumps(payload))

                # Check the response
                if response.status_code == 200:
                    moderation_result_response = response.json()
                    print("Moderation response:", json.dumps(moderation_result_response, indent=2))
                else:
                    print(f"Error: {response.status_code} - {response.text}")

                print(moderation_result_response)
                # Initialize the custom moderation result format
                moderation_result = {
                    "C1(Sexual Content)": False,
                    "C2(Harassment & Bullying)": False,
                    "C3(Threats, Violence & Harm)": False,
                    "C4(False & Deceptive Information)": False,
                    "C5(Illegal/Regulated Activities)": False,
                    "C6(Hateful Content & Extremism)": False
                }

                # Map the categories and severity to your custom categories
                for category_analysis in moderation_result_response["categoriesAnalysis"]:
                    category = category_analysis["category"]
                    severity = category_analysis["severity"]

                    # Check the severity and map to custom categories
                    if category == "Sexual" and severity > 0:
                        moderation_result["C1(Sexual Content)"] = True
                    if category == "Violence" and severity > 0 and severity <= 4:
                        moderation_result["C2(Harassment & Bullying)"] = True
                    if category == "Violence" and severity > 4:
                        moderation_result["C3(Threats, Violence & Harm)"] = True
                    if category == "SelfHarm" and severity > 0:
                        moderation_result["C6(Hateful Content & Extremism)"] = True
                    if category == "Hate" and severity > 0:
                        moderation_result["C6(Hateful Content & Extremism)"] = True

                # Prepare the response format
                response = f"""
                VIDEO_CONTENT: NA
                VIOLATE_REASON: NA
                {json.dumps(moderation_result, indent=2)}
                """

                return response, 1

