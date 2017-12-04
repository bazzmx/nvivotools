#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2016 Jonathan Schultz
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import argparse
from NVivoNorm import NVivoNorm
from sqlalchemy import *
import re
import unicodecsv
import shutil

def add_arguments(parser):
    parser.description = "Query taggings in a normalised file."

    generalgroup = parser.add_argument_group('General')
    generalgroup.add_argument(      'infile',   type=str,
                                                help='Input normalised NVivo (.norm) file')
    generalgroup.add_argument('-o', '--outfile', type=str,
                                                 help='Output file')
    generalgroup.add_argument('-s',  '--source',          type=lambda s: unicode(s, 'utf8'))
    generalgroup.add_argument('-sc', '--source-category', type=lambda s: unicode(s, 'utf8'))
    generalgroup.add_argument('-n',  '--node',            type=lambda s: unicode(s, 'utf8'))
    generalgroup.add_argument('-nc', '--node-category',   type=lambda s: unicode(s, 'utf8'))

    advancedgroup = parser.add_argument_group('Advanced')
    advancedgroup.add_argument('-v', '--verbosity',  type=int, default=1)
    advancedgroup.add_argument('--no-comments', action='store_true', help='Do not produce a comments logfile')

    parser.set_defaults(func=queryTagging)
    parser.set_defaults(build_comments=build_comments)
    parser.set_defaults(hiddenargs=['hiddenargs', 'verbosity', 'no_comments'])


def parse_arguments():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    return vars(parser.parse_args())

def build_comments(kwargs):
    comments = ((' ' + kwargs['outfile'] + ' ') if kwargs['outfile'] else '').center(80, '#') + '\n'
    comments += '# ' + os.path.basename(__file__) + '\n'
    hiddenargs = kwargs['hiddenargs'] + ['hiddenargs', 'func', 'build_comments']
    for argname, argval in kwargs.iteritems():
        if argname not in hiddenargs:
            if type(argval) == str or type(argval) == unicode:
                comments += '#     --' + argname + '="' + argval + '"\n'
            elif type(argval) == bool:
                if argval:
                    comments += '#     --' + argname + '\n'
            elif type(argval) == list:
                for valitem in argval:
                    if type(valitem) == str:
                        comments += '#     --' + argname + '="' + valitem + '"\n'
                    else:
                        comments += '#     --' + argname + '=' + str(valitem) + '\n'
            elif argval is not None:
                comments += '#     --' + argname + '=' + str(argval) + '\n'

    return comments

def queryTagging(infile, outfile,
                 source, source_category, node, node_category,
                 verbosity, no_comments,
                 comments, **dummy):

    try:
        if not no_comments:
            if outfile:
                logfilename = outfile.rsplit('.',1)[0] + '.log'
                if os.path.exists(logfilename):
                    shutil.move(logfilename, logfilename + '.bak')
                logfile = open(logfilename, 'w')
                logfile.write(comments)
                logfile.close()
            else:
                print(comments)

        norm = NVivoNorm(infile)
        norm.begin()

        sourcesel = select([
                norm.Source.c.Name.label('Source'),
                norm.Source.c.Content,
                norm.Node.c.Name.label('Node'),
                norm.Tagging.c.Fragment
            ]).where(and_(
                norm.Source.c.Id == norm.Tagging.c.Source,
                norm.Tagging.c.Node == norm.Node.c.Id
            ))

        if source:
            sourcesel = sourcesel.where(
                norm.Source.c.Name == bindparam('Source')
            )
        if source_category:
            sourcesel = sourcesel.where(and_(
                norm.Source.c.Category == norm.SourceCategory.c.Id,
                norm.SourceCategory.c.Name == bindparam('SourceCategory')
            ))
        if node:
            sourcesel = sourcesel.where(and_(
                norm.Tagging.c.Node == norm.Node.c.Id,
                norm.Node.c.Name == bindparam('Node')
            ))
        if node_category:
            sourcesel = sourcesel.where(and_(
                norm.Tagging.c.Node == norm.Node.c.Id,
                norm.Node.c.Category == norm.NodeCategory.c.Id,
                norm.NodeCategory.c.Name == bindparam('NodeCategory')
            ))

        taggings = norm.con.execute(sourcesel, {
                'Source':         source,
                'SourceCategory': source_category,
                'Node':           node,
                'NodeCategory':   node_category
            })

        if outfile:
            if os.path.exists(outfile):
                shutil.move(outfile, outfile + '.bak')

            csvfile = file(outfile, 'w')
        else:
            csvfile = sys.stdout

        if not no_comments:
            csvfile.write(comments)

        csvwriter = unicodecsv.DictWriter(csvfile,
                                          fieldnames=['Source', 'Node', 'Text', 'Fragment'],
                                          extrasaction='ignore',
                                          lineterminator=os.linesep,
                                          quoting=unicodecsv.QUOTE_NONNUMERIC)

        csvwriter.writeheader()

        taggings = [dict(tagging) for tagging in taggings]
        for tagging in taggings:
            matchfragment = re.match("(?P<startX>[0-9]+):(?P<endX>[0-9]+)(?:,(?P<startY>[0-9]+)(?::(?P<endY>[0-9]+))?)?",
                                     tagging['Fragment'])
            startX = int(matchfragment.group('startX'))
            endX   = int(matchfragment.group('endX'))
            tagging['startX'] = startX
            tagging['endX']   = endX
            tagging['Text']   = tagging['Content'][startX:endX+1]

        taggings = sorted(taggings, key=lambda tagging: (tagging['Source'], tagging['startX']))

        csvwriter.writerows(taggings)
        csvfile.close()

    except:
        raise

    finally:
        del norm

def main():
    kwargs = parse_arguments()
    kwargs['comments'] = build_comments(kwargs)
    kwargs['func'](**kwargs)

if __name__ == '__main__':
    main()