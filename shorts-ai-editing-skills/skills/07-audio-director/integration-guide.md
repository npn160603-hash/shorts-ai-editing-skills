# Tích hợp Skill 07
1. Pass 1: `measure_cmd(video_after_cut)` → `parse_loudnorm_json`. (Đo trên bản mix tạm nếu có nhạc/SFX.)
2. Pass 2 (export): `ffmpeg -i cut.mp4 [-stream_loop -1 -i music.wav] [-i sfx...] -filter_complex "<ffmpeg_mix_graph(plan, measured)>" -map 0:v -map "[amix]" -c:v copy -c:a aac -b:a 192k -t <duration> out/rev-<n>/final.mp4`.
3. Nếu video cũng re-encode (camera/caption), gộp graph video + audio trong cùng `-filter_complex`.
4. UI: chọn file nhạc + chọn license (own/CC0/licensed) + ô bằng chứng; thư viện SFX là thư mục dự án + `library.json`.
5. Toggle OFF → giữ audio sau cắt, không normalise.
