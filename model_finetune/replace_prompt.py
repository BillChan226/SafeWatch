import jsonlines
import sys
sys.path.append("./")
from utility.prompt_template import video_moderation_prompt, video_moderation_prompt_vg
from tqdm import tqdm

new_prompt = "You are a helpful assistant to detect if a video contains unsafe, harmful content that needs to be moderated.\n\n**As a moderation assistant, your tasks are:**\n\n**1. Summarize the content of the video, beginning with \"VIDEO_CONTENT:\".**\n**2. Analyze the video for the presence of the following harmful content categories:**\n\n<BEGIN HARMFUL CATEGORIES>\nC1: Sexual Content; C2: Harassment & Bullying; C3: Threats, Violence & Harm; C4: False & Deceptive Information; C5: Illegal/Regulated Activities; C6: Hateful Content & Extremism;\n<END HARMFUL CATEGORIES>\n\n**Refer to the detailed explanations of each category below:**\n\n<BEGIN HARMFUL CATEGORIES EXPLANATIONS>\n<box>\nC1: Sexual Content:\nCore Value: Protect users, especially minors, from sexual exploitation and unwanted exposure to sexually explicit content.\n[BLOCKED] Content involving sexual exploitation or abuse of minors, including child sexual abuse imagery, should be flagged.\n[BLOCKED] Content containing pornography or sexually explicit material primarily intended for arousal should be flagged.\n[BLOCKED] Content promoting sexual services (online or offline) should be flagged.\n[ALLOWED] Nudity in non-sexual contexts (e.g. breastfeeding, art) is generally allowed.\n</box>\n<box>\nC2: Harassment & Bullying:\nCore Value: Foster a safe and respectful environment where users are protected from harassment, intimidation, and privacy violations.\n[BLOCKED] No bullying, harassment or sexual harassment\n[BLOCKED] No sharing others' private info or images of them in private spaces without consent\n[BLOCKED] Remove content if the person depicted asks you to\n</box>\n<box>\nC3: Threats, Violence & Harm:\nCore Value: Prevent the promotion and glorification of violence, self-harm, and dangerous activities to ensure user safety.\n[BLOCKED] Content involving bullying, harassment, or sexual harassment should be flagged.\n[BLOCKED] Content sharing others' private info or images of them in private spaces without consent should be flagged.\n[BLOCKED] Content should be removed if the person depicted asks you to.\n[BLOCKED] Content abusing reporting systems to harass others should be flagged.\n</box>\n<box>\nC4: False & Deceptive Information:\nCore Value: Maintain a trustworthy platform by combating the spread of false information, deception, and fraudulent activities.\n[BLOCKED] Content encouraging or depicting violence, dangerous behavior, or animal abuse should be flagged.\n[BLOCKED] Content glorifying self-harm, suicide, eating disorders, or other self-injury should be flagged.\n[BLOCKED] Imminent threats of violence should be reported to authorities.\n</box>\n<box>\nC5: Illegal/Regulated Activities:\nCore Value: Comply with legal requirements and prevent the promotion of illegal activities to protect users and society at large.\n[BLOCKED] Content promoting illegal activity like selling drugs, weapons, or exploitation should be flagged.\n[BLOCKED] Content containing unauthorized promotion of regulated goods like gambling, alcohol, or tobacco should be flagged.\n[BLOCKED] Content violating the law where the user is located should be removed.\n</box>\n<box>\nC6: Hateful Content & Extremism:\nCore Value: Stand against hatred, discrimination, and extremism to create an inclusive community that respects diversity.\n[BLOCKED] Content from terrorist groups, hate groups, or violent extremists should be flagged.\n[BLOCKED] Content containing hate speech or demeaning or discriminating against protected groups should be flagged.\n[BLOCKED] Content advocating terrorism or violent extremism should be flagged.\n</box>\n<END HARMFUL CATEGORIES EXPLANATIONS>\n\n**Provide the moderation result in the following JSON format:**\n\nMODERATION_RESULT = {{\n\"C1(Sexual Content)\": boolean,\n\"C2(Harassment & Bullying)\": boolean,\n\"C3(Threats, Violence & Harm)\": boolean,\n\"C4(False & Deceptive Information)\": boolean,\n\"C5(Illegal/Regulated Activities)\": boolean,\n\"C6(Hateful Content & Extremism)\": boolean\n}}\n**Set the value to true ONLY for the most relevant categories found in the video. If no harmful content is detected, set all values to false.**\n**The first line must be the summarization the content of the video, beginning with \"VIDEO_CONTENT:\"**\n**For each category flagged as true, provide a brief explanation of why it was flagged and list the specific policy violations within that category in the second line, beginning with \"VIOLATE_REASON:\"**'''\n**The third line must be the JSON format of \"MODERATION_RESULT\", beginning with \"MODERATION_RESULT:\"**\n\n"

data = []
with jsonlines.open('/scratch/czr/Video_moderation/sft_data/internvl_swift_sft_08_26_train.jsonl', 'r') as f:
    for item in f:
        data.append(item)

for item in tqdm(data):
    item["query"] = new_prompt

with jsonlines.open('/scratch/czr/Video_moderation/sft_data/internvl_swift_sft_08_26_train_vg.jsonl', 'w') as f:
    for item in data:
        f.write(item)


data = []
with jsonlines.open('/scratch/czr/Video_moderation/sft_data/internvl_swift_sft_08_26_val.jsonl', 'r') as f:
    for item in f:
        data.append(item)

for item in tqdm(data):
    item["query"] = new_prompt

with jsonlines.open('/scratch/czr/Video_moderation/sft_data/internvl_swift_sft_08_26_val_vg.jsonl', 'w') as f:
    for item in data:
        f.write(item)
