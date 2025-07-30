import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from rich.padding import Padding
from rich.rule import Rule

from unshackle.core.binaries import DoviTool
from unshackle.core.config import config
from unshackle.core.console import console


class Hybrid:
    def __init__(self, videos, source) -> None:
        self.log = logging.getLogger("hybrid")

        """
            Takes the Dolby Vision and HDR10(+) streams out of the VideoTracks.
            It will then attempt to inject the Dolby Vision metadata layer to the HDR10(+) stream.
            """
        global directories
        from unshackle.core.tracks import Video

        self.videos = videos
        self.source = source
        self.rpu_file = "RPU.bin"
        self.hdr_type = "HDR10"
        self.hevc_file = f"{self.hdr_type}-DV.hevc"

        console.print(Padding(Rule("[rule.text]HDR10+DV Hybrid"), (1, 2)))

        for video in self.videos:
            if not video.path or not os.path.exists(video.path):
                self.log.exit(f" - Video track {video.id} was not downloaded before injection.")

        if not any(video.range == Video.Range.DV for video in self.videos) or not any(
            video.range == Video.Range.HDR10 for video in self.videos
        ):
            self.log.exit(" - Two VideoTracks available but one of them is not DV nor HDR10(+).")

        if os.path.isfile(config.directories.temp / self.hevc_file):
            self.log.info("✓ Already Injected")
            return

        for video in videos:
            # Use the actual path from the video track
            save_path = video.path
            if not save_path or not os.path.exists(save_path):
                self.log.exit(f" - Video track {video.id} was not downloaded or path not found: {save_path}")

            if video.range == Video.Range.HDR10:
                self.extract_stream(save_path, "HDR10")
            elif video.range == Video.Range.DV:
                self.extract_stream(save_path, "DV")
                # self.extract_dv_stream(video, save_path)

        self.extract_rpu([video for video in videos if video.range == Video.Range.DV][0])
        if os.path.isfile(config.directories.temp / "RPU_UNT.bin"):
            self.rpu_file = "RPU_UNT.bin"
            self.level_6()
            # Mode 3 conversion already done during extraction when not untouched
        elif os.path.isfile(config.directories.temp / "RPU.bin"):
            # RPU already extracted with mode 3
            pass

        self.injecting()

        self.log.info("✓ Injection Completed")
        if self.source == ("itunes" or "appletvplus"):
            Path.unlink(config.directories.temp / "hdr10.mkv")
            Path.unlink(config.directories.temp / "dv.mkv")
        Path.unlink(config.directories.temp / "DV.hevc")
        Path.unlink(config.directories.temp / "HDR10.hevc")
        Path.unlink(config.directories.temp / f"{self.rpu_file}")

    def ffmpeg_simple(self, save_path, output):
        """Simple ffmpeg execution without progress tracking"""
        p = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-i",
                str(save_path),
                "-c:v",
                "copy",
                str(output),
                "-y",  # overwrite output
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return p.returncode

    def extract_stream(self, save_path, type_):
        output = Path(config.directories.temp / f"{type_}.hevc")

        self.log.info(f"+ Extracting {type_} stream")

        returncode = self.ffmpeg_simple(save_path, output)

        if returncode:
            output.unlink(missing_ok=True)
            self.log.error(f"x Failed extracting {type_} stream")
            sys.exit(1)

    def ffmpeg_task(self, save_path, output, task_id):
        p = subprocess.Popen(
            [
                "ffmpeg",
                "-nostdin",
                "-i",
                str(save_path),
                "-c:v",
                "copy",
                str(output),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        )

        self.progress.start_task(task_id)

        for line in p.stderr:
            if "frame=" in line:
                self.progress.update(task_id, advance=0)
        p.wait()

        return p.returncode

    def extract_hdr10_stream(self, video, save_path):
        type_ = "HDR10"
        if os.path.isfile(Path(config.directories.temp / f"{type_}.hevc")):
            return
        if self.source == "itunes" or self.source == "appletvplus":
            self.log.info("+ Muxing HDR10 stream for fixing MP4 file")
            subprocess.run(
                [
                    "mkvmerge",
                    "-o",
                    Path(config.directories.temp / "hdr10.mkv"),
                    save_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.log.info(f"+ Extracting {type_} stream")
            extract_stream = subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-stats",
                    "-i",
                    Path(config.directories.temp / "hdr10.mkv"),
                    "-c:v",
                    "copy",
                    Path(config.directories.temp / f"{type_}.hevc"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if extract_stream.returncode:
                Path.unlink(Path(config.directories.temp / f"{type_}.hevc"))
                self.log.error(f"x Failed extracting {type_} stream")
                sys.exit(1)
        else:
            extract_stream = subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-stats",
                    "-i",
                    save_path,
                    "-c:v",
                    "copy",
                    Path(config.directories.temp / f"{type_}.hevc"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if extract_stream.returncode:
                Path.unlink(Path(config.directories.temp / f"{type_}.hevc"))
                self.log.error(f"x Failed extracting {type_} stream")
                sys.exit(1)

    def extract_dv_stream(self, video, save_path):
        type_ = "DV"
        if os.path.isfile(Path(config.directories.temp / f"{type_}.hevc")):
            return
        if self.source == "itunes" or self.source == "appletvplus":
            self.log.info("+ Muxing Dolby Vision stream for fixing MP4 file")
            subprocess.run(
                [
                    "mkvmerge",
                    "-o",
                    Path(config.directories.temp / "dv.mkv"),
                    save_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.log.info("+ Extracting Dolby Vision stream")
            extract_stream = subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-stats",
                    "-i",
                    Path(config.directories.temp / "dv.mkv"),
                    "-an",
                    "-c:v",
                    "copy",
                    "-f",
                    "hevc",
                    Path(config.directories.temp / "out_1.h265"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if extract_stream.returncode:
                Path.unlink(Path(config.directories.temp / f"{type_}.hevc"))
                self.log.error(f"x Failed extracting {type_} stream")
                sys.exit(1)
        else:
            extract_stream = subprocess.run(
                [
                    "mp4demuxer",
                    "--input-file",
                    save_path,
                    "--output-folder",
                    Path(config.directories.temp),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if extract_stream.returncode:
                Path.unlink(Path(config.directories.temp / f"{type_}.hevc"))
                self.log.error(f"x Failed extracting {type_} stream")
                sys.exit(1)

    def extract_rpu(self, video, untouched=False):
        if os.path.isfile(config.directories.temp / "RPU.bin") or os.path.isfile(
            config.directories.temp / "RPU_UNT.bin"
        ):
            return

        self.log.info(f"+ Extracting{' untouched ' if untouched else ' '}RPU from Dolby Vision stream")

        extraction_args = [str(DoviTool)]
        if not untouched:
            extraction_args += ["-m", "3"]
        extraction_args += [
            "extract-rpu",
            config.directories.temp / "DV.hevc",
            "-o",
            config.directories.temp / f"{'RPU' if not untouched else 'RPU_UNT'}.bin",
        ]

        rpu_extraction = subprocess.run(
            extraction_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if rpu_extraction.returncode:
            Path.unlink(config.directories.temp / f"{'RPU' if not untouched else 'RPU_UNT'}.bin")
            if b"MAX_PQ_LUMINANCE" in rpu_extraction.stderr:
                self.extract_rpu(video, untouched=True)
            elif b"Invalid PPS index" in rpu_extraction.stderr:
                self.log.exit("x Dolby Vision VideoTrack seems to be corrupt")
            else:
                self.log.exit(f"x Failed extracting{' untouched ' if untouched else ' '}RPU from Dolby Vision stream")

    def level_6(self):
        """Edit RPU Level 6 values"""
        with open(config.directories.temp / "L6.json", "w+") as level6_file:
            level6 = {
                "cm_version": "V29",
                "length": 0,
                "level6": {
                    "max_display_mastering_luminance": 1000,
                    "min_display_mastering_luminance": 1,
                    "max_content_light_level": 0,
                    "max_frame_average_light_level": 0,
                },
            }

            json.dump(level6, level6_file, indent=3)

        if not os.path.isfile(config.directories.temp / "RPU_L6.bin"):
            self.log.info("+ Editing RPU Level 6 values")
            level6 = subprocess.run(
                [
                    str(DoviTool),
                    "editor",
                    "-i",
                    config.directories.temp / self.rpu_file,
                    "-j",
                    config.directories.temp / "L6.json",
                    "-o",
                    config.directories.temp / "RPU_L6.bin",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if level6.returncode:
                Path.unlink(config.directories.temp / "RPU_L6.bin")
                self.log.exit("x Failed editing RPU Level 6 values")

            # Update rpu_file to use the edited version
            self.rpu_file = "RPU_L6.bin"

    def mode_3(self):
        """Convert RPU to Mode 3"""
        with open(config.directories.temp / "M3.json", "w+") as mode3_file:
            json.dump({"mode": 3}, mode3_file, indent=3)

        if not os.path.isfile(config.directories.temp / "RPU_M3.bin"):
            self.log.info("+ Converting RPU to Mode 3")
            mode3 = subprocess.run(
                [
                    str(DoviTool),
                    "editor",
                    "-i",
                    config.directories.temp / self.rpu_file,
                    "-j",
                    config.directories.temp / "M3.json",
                    "-o",
                    config.directories.temp / "RPU_M3.bin",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if mode3.returncode:
                Path.unlink(config.directories.temp / "RPU_M3.bin")
                self.log.exit("x Failed converting RPU to Mode 3")

        self.rpu_file = "RPU_M3.bin"

    def injecting(self):
        if os.path.isfile(config.directories.temp / self.hevc_file):
            return

        self.log.info(f"+ Injecting Dolby Vision metadata into {self.hdr_type} stream")

        inject = subprocess.run(
            [
                str(DoviTool),
                "inject-rpu",
                "-i",
                config.directories.temp / f"{self.hdr_type}.hevc",
                "--rpu-in",
                config.directories.temp / self.rpu_file,
                "-o",
                config.directories.temp / self.hevc_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if inject.returncode:
            Path.unlink(config.directories.temp / self.hevc_file)
            self.log.exit("x Failed injecting Dolby Vision metadata into HDR10 stream")
