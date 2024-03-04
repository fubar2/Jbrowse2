import argparse
import logging
import os
import sys

from jbrowse2 import JbrowseConnector as jbC

logging.basicConfig(level=logging.debug)
log = logging.getLogger("jbrowse")


def makeDefaultLocation():

    refName = jc.genome_firstcontig
    defloc = "%s:100..10000" % refName
    return defloc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="", epilog="")
    parser.add_argument("--sessName", help="Session name", default="AutoJBrowse")
    parser.add_argument(
        "--trackmeta",
        help="Repeatable 'filename,filext,filepath,[bai/crai path for filesystem bam/cram]' for JBrowse2 tracks",
        default=[],
        action="append",
    )
    parser.add_argument(
        "--referencemeta",
        help="Repeatable 'filename, filext, filepath, ... ,' for JBrowse2 reference tracks - usually only one needed",
        default=[],
        action="append",
    )
    parser.add_argument(
        "--pafmeta",
        help="Repeatable. Each is a 'pafname, filext, filepath, ... ,' for a JBrowse2 paf track",
        default=[],
        action="append",
    )
    parser.add_argument(
        "--pafreferencemeta",
        help="Repeatable. Each is a 'pafname,refpath,refname' Every pafname must have one or more",
        default=[],
        action="append",
    )
    parser.add_argument(
        "--jbrowse2path", help="Path to JBrowse2 directory in biocontainer or Conda"
    )
    parser.add_argument("--outdir", help="Output directory", required=True)
    parser.add_argument("--version", "-V", action="version", version="%(prog)s 2.10.2")
    args = parser.parse_args()
    sessName = args.sessName
    # --trackmeta $jbrowseme[$key],$jbrowseme[$key].ext,'$key'
    trackList = [x.strip().split(",") for x in args.trackmeta if x > ""]
    refList = [x.strip().split(",") for x in args.referencemeta if x > ""]
    if len(refList) > 0:
        listgenomes = [f for f in refList if f[1] in ["fasta", "fasta.gz"]]
        # assume no pafs here
        if len(listgenomes) > 0:
            genome_paths = [x[0] for x in listgenomes]
            genome_names = [x[2] for x in listgenomes]
            guseuri = []
            for x in genome_paths:
                if x.startswith('http://') or x.startswith('https://'):
                    guseuri.append('yes')
                else:
                    guseuri.append('no')
            jc = jbC(
                outdir=args.outdir,
                jbrowse2path=args.jbrowse2path,
                genomes=[
                    {
                        "path": x,
                        "label": genome_names[i],
                        "useuri": guseuri[i],
                        "meta":  {"name": genome_names[i],
                                            "dataset_dname": genome_names[i]
                                        }
                    }
                    for i, x in enumerate(genome_paths)
                ],
            )

            jc.process_genomes()
            default_session_data = {
                "visibility": {
                    "default_on": [],
                    "default_off": [],
                },
                "style": {},
                "style_labels": {},
            }

            listtracks = trackList
            # foo.paf must have a foo_paf.fasta or fasta.gz to match
            tnames = [x[2] for x in listtracks]
            texts = [x[1] for x in listtracks]
            for i, track in enumerate(listtracks):
                tpath, trext, trackname = track[:3]
                if trext == "paf":
                    refname = trackname + "_paf.fasta"
                    refdat = [x[2] for x in listtracks if x[2] == refname]
                    if not refdat:
                        jc.logging.warn(
                            "!! No reference file %s corresponding to paf file %s found. Not building - there must be a corresponding fasta for each paf"
                            % (refname, trackname)
                        )
                        sys.exit(3)
                    else:
                        track_conf = {
                            "conf": {
                                "options": {
                                    "paf": {"genome": refdat, "genome_label": trackname}
                                }
                            }
                        }
                elif trext == "bam":
                    ipath  = track[3]
                    if not os.path.exists(ipath):
                        ipath = os.path.realpath(os.path.join(jc.outdir, trackname + '.bai'))
                        cmd = ["samtools", "index", "-b", "-o", ipath, os.path.realpath(track[0])]
                        sys.stdout.write('#### calling %s' % ' '.join(cmd))
                        jc.subprocess_check_call(cmd)
                    track_conf = {"conf": {"options": {"bam": {"bam_index": ipath}}}}
                elif trext == "cram":
                    ipath  = track[3]
                    if not os.path.exists(ipath):
                        jc.logging.info('calling %s' % ' '.join(cmd))
                        ipath = os.path.realpath(os.path.join('./', trackname + '.crai'))
                        cmd = ["samtools", "index", "-c", "-o", ipath, os.path.realpath(track[0])]
                        sys.stdout.write('#### calling %s' % ' '.join(cmd))
                        jc.subprocess_check_call(cmd)
                    track_conf = {"conf": {"options": {"cram": {"cram_index": ipath}}}}
                else:
                    track_conf = {}
                track_conf["format"] = trext
                track_conf["name"] = trackname
                track_conf["label"] = trackname
                useu = tpath.startswith('http://') or tpath.startswith('https://')
                useuri = 'no'
                if useu:
                    useuri = 'yes'
                track_conf["trackfiles"] = [
                    (tpath, trext, useuri, trackname, {}),
                ]
                track_conf["category"] = "Autogenerated"
                keys = jc.process_annotations(track_conf)

                if keys:
                    for key in keys:
                        if trext in [
                            "bigwig",
                            "gff3",
                            "gff",
                            "vcf",
                            "maf",
                        ]:
                            default_session_data["visibility"]["default_on"].append(key)
                        else:
                            default_session_data["visibility"]["default_off"].append(
                                key
                            )
            # general_data = {
            # "analytics": root.find("metadata/general/analytics").text,
            # "primary_color": root.find("metadata/general/primary_color").text,
            # "secondary_color": root.find("metadata/general/secondary_color").text,
            # "tertiary_color": root.find("metadata/general/tertiary_color").text,
            # "quaternary_color": root.find("metadata/general/quaternary_color").text,
            # "font_size": root.find("metadata/general/font_size").text,
            # }
            # jc.add_general_configuration(general_data)
            trackconf = jc.config_json.get("tracks", None)
            if trackconf:
                jc.config_json["tracks"].update(jc.tracksToAdd)
            else:
                jc.config_json["tracks"] = jc.tracksToAdd
            jc.write_config()
            defLoc = makeDefaultLocation()
            default_session_data.update(
                {"defaultLocation": defLoc, "session_name": sessName}
            )
            track_conf.update(default_session_data)
            jc.add_default_session(default_session_data)
            # jc.text_index() not sure what broke here.
    else:
        sys.stderr.write(
            "!!!! Collection has no suitable trackfiles for autogenJB2 - nothing to process"
        )
