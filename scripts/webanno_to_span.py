from glob import glob
import pandas as pd
import re

# where to find your cleaned TSVs:
appraisal_projectpath = input('Path to appraisal project folder: (e.g. C:/.../Appraisal/clean_TSVs)')
# where to write a new CSV
appraisal_writepath = input('Path to write a new appraisal CSV to: (e.g. C:/.../combined_appraisal_comments.csv)')
# same for negation
negation_projectpath = input('Path to negation project folder: (e.g. C:/.../Negation/clean_TSVs)')
negation_writepath = input('Path to write a new negation CSV to: (e.g. C:/.../combined_negation_comments.csv)')
# where to find the mapping CSV so that names like source_x_x and aboriginal_1 are both used:
mapping_csv = input("Path to your mapping of names e.g. 'C:/.../comment_counter_appraisal_mapping.csv'")

# these are the actual column headers for the TSV files
# some Appraisal TSVs do not have graduation, hence the need for two lists of names
appraisal_longheaders = ['sentpos', 'charpos', 'word', 'attlab', 'attpol', 'gralab', 'grapol']
appraisal_shortheaders = ['sentpos', 'charpos', 'word', 'attlab', 'attpol']
negation_headers = ['sentpos', 'charpos', 'word', 'negation']
# some comments have no annotations
no_annotation = ['sentpos', 'charpos', 'word']
appraisal_possnames = [no_annotation, appraisal_shortheaders, appraisal_longheaders]
negation_possnames = [no_annotation, negation_headers]


def getcontents(directory):
    """
    Returns the file paths for all files in the specified path (directory). Identical to glob.glob() except that it
    converts '\\' to '/'
    """
    return [name.replace('\\', '/') for name in glob(directory + '/*')]


appraisal_projectdirs = getcontents(appraisal_projectpath)
negation_projectdirs = getcontents(negation_projectpath)


def readprojfile(source, project):
    """
    Reads a cleaned WebAnno TSV into a pandas dataframe. One column is often read as full of NaN's due to the TSVs'
    original formatting, so this function drops any columns with NaN's.

    :param source: the path to the TSV
    :param possnames: the headers that may occur in the TSV, as a list of lists of headers.
        The function will check each list within possnames to see if its length is equal to the number of columns
    :param project: 'app' if Appraisal, 'neg' if negation.
    :return: a pandas dataframe containing the information in the original TSV
    """
    # set possnames
    if project == "neg" or project.lower() == "negation":
        possnames = negation_possnames
        project = "neg"
    elif project == "app" or project.lower() == "appraisal":
        possnames = appraisal_possnames
        project = "app"
    else:
        print("Project type not recognized. Use 'neg' or 'att'.")
        possnames = None

    newdf = pd.read_csv(source, sep='\t', header=None)
    newdf = newdf.dropna(axis=1, how='all')
    if (project == "neg" or project.lower() == "negation")\
            and len(newdf.columns) == 5:        # Neg annotations with arrows have an extra column we won't use
        newdf = newdf.loc[:, 0:3]               # so we'll just delete it
    for headers in possnames:
        if len(newdf.columns) == len(headers):
            newdf.columns = headers
    if all([len(newdf.columns) != i for i in [len(headers) for headers in possnames]]):
        print("No correct number of columns in", source)
    return newdf


# the labels that can show up in different columns
attlabs = ('Appreciation', 'Affect', 'Judgment')
attpols = ('pos', 'neu', 'neg')
gralabs = ('Force', 'Focus')
grapols = ('up', 'down')

neglabs = ('NEG', 'SCOPE', 'FOCUS', 'XSCOPE')

# create some tuples to show which columns go with which labels
appraisal_collabels = ((appraisal_longheaders[3], attlabs),
                       (appraisal_longheaders[4], attpols),
                       (appraisal_longheaders[5], gralabs),
                       (appraisal_longheaders[6], grapols))
# this next tuple is within another tuple so that the same commands we need later will iterate correctly
negation_collabels = (('negation', neglabs),)

# create a dictionary matching old comment names to comment counter ones
if mapping_csv:
    mapping1 = pd.read_csv(mapping_csv)
    list1 = mapping1['appraisal_negation_annotation_file_name'].tolist()
    list2 = mapping1['comment_counter'].tolist()
    # dictionary of original to comment counter names
    mappingdict1 = {}
    for i in range(max(len(list1), len(list2))):
        mappingdict1[list1[i]] = list2[i]
    # same dictionary in reverse
    mappingdict2 = {}
    for i in range(max(len(list1), len(list2))):
        mappingdict2[list2[i]] = list1[i]


def getlabinds_df(dataframe, correspondences, dfname="dataframe", verbose=False):
    """
    Gets the unique labels, including indices, that appear in a dataframe so that they can be searched later.

    :param dataframe: a pandas dataframe
    :param correspondences: a list or tuple of columns and labels like collabels
    :param dfname: a name for the dataframe, used for reporting when one or more columns doesn't show up
    :param verbose: a boolean; if True, tells you when a dataframe is missing a column
    :return: a list of the form [(index of column),(list of unique labels including index of that label, e.g.
    ['Appreciation','Appreciation[1]','Appreciation[2]'])
    """
    newdict = {}
    for entry in range(len(correspondences)):
        if correspondences[entry][0] in dataframe.columns:
            searchedlist = dataframe[correspondences[entry][0]].tolist()
            splitlist = [i.split('|') for i in searchedlist]
            foundlist = []
            for e in splitlist:  # each element in splitlist is currently a list
                for i in e:  # so i is a string
                    foundlist.append(i)  # so now foundlist is a list of strings
            foundlist = set(foundlist)  # convert to set so we have uniques only
            foundlist = [label for label in foundlist]  # convert foundlist back to a list
            newdict[correspondences[entry][0]] = foundlist
        else:
            if verbose:
                print(dfname, "does not include column", correspondences[entry][0])
    return newdict


def lookup_label(dataframe, column, label, commentid="dataframe", not_applicable=None, verbose=False,
                 clean_suffix='_cleaned.tsv'):
    """
    Looks in the dataframe for rows matching the label and returns them.

    :param dataframe: A pandas dataframe
    :param column: which column in the dataframe to look in for the labels
    :param label: which label to look for in the column
    :param commentid: the name of the comment; the new row will have this as its first entry
    :param bothids: whether to include both comment names (e.g. aboriginal_1 and source_xx_xx)
    :param not_applicable: what to put in a cell if there is no data (e.g. something un-annotated)
    :param verbose: whether to tell you when it's done
    :param clean_suffix: the suffix appended to clean files. Default assumes you cleaned them with clean_comments.py
    :return: a list that can be used as a new row or rows. If the label has no index (e.g. 'Appreciation' or '_'), then
        all rows with those labels will be returned. If it has an index (e.g. 'Appreciation[3]'), then one row
        representing that annotated span will be returned.
        The fields in the list are, by column:
            - the comment ID
            - which sentence the span starts in
            - which sentence it ends in
            - which character it starts on
            - which character it ends on
            - which words are in the span
            - the Attitude label for the span
            - the Attitude polarity for the span
            - the graduation label for the span
            - the graduation polarity for the span
    """
    # determine if we're looking at attitude, graduation, or negation
    if 'att' in column:
        layer = 'att'
    elif 'gra' in column:
        layer = 'gra'
    elif column == 'negation':
        layer = 'neg'
    else:
        layer = 'unknown'

    # Check that both label and polarity columns are present
    if ('attlab' in dataframe.columns) ^ ('attpol' in dataframe.columns):
        if 'attlab' in dataframe.columns:
            print(commentid, 'has attlab column but no attpol column')
        if 'attpol' in dataframe.columns:
            print(commentid, 'has attpol column but no attlab column')
    if ('gralab' in dataframe.columns) ^ ('grapol' in dataframe.columns):
        if 'gralab' in dataframe.columns:
            print(commentid, 'has gralab column but no grapol column')
        if 'grapol' in dataframe.columns:
            print(commentid, 'has grapol column but no gralab column')

    # look for labels with brackets (e.g. 'Appreciation[3]')
    if '[' in label:
        mask = [(label in i) for i in dataframe[column].tolist()]
        founddf = dataframe[mask]
        # get the sentence(s) of the label
        foundsentstart = int(re.search(r'^.*-', founddf['sentpos'].tolist()[0]).group()[:-1])
        foundsentend = int(re.search(r'^.*-', founddf['sentpos'].tolist()[-1]).group()[:-1])

        # get the character positions for the new row
        # look at which character the label starts in
        foundcharstart = int(re.search(r'^.*-', founddf['charpos'].tolist()[0]).group()[:-1])
        # look at which character the label ends in
        foundcharend = int(re.search(r'-.*$', founddf['charpos'].tolist()[-1]).group()[1:])

        # concatenate the words for the new row
        foundwords = ''
        for word in founddf['word']:
            foundwords = foundwords + word + ' '
        foundwords = foundwords[:-1]

        # get the labels for the new row
        # in case of pipes, figure out which one is the real label
        posslabels = founddf[column].tolist()
        posslabels = posslabels[0]
        posslabels = posslabels.split('|')
        labelindex = posslabels.index(label)

        # now look through the columns and find the appropriate labels
        # Each column is converted to a list. The first item in the list is used to find the label.
        # This item is split by '|' in case of stacked annotations.
        # Before, we found the index of the label we want. We get the found label from this index.
        if layer == 'att':
            if 'attlab' in founddf.columns:
                foundattlab = founddf['attlab'].tolist()[0].split('|')[labelindex]
                # We want to cut off the index (e.g. 'Appreciation[3]' -> 'Appreciation')
                # search() finds everything up to the '[', and .group()[:-1] returns what it found, minus the '['
                foundattlab = re.search(r'^.*\[', foundattlab).group()[:-1]
            else:
                foundattlab = not_applicable
            if 'attpol' in founddf.columns:
                foundattpol = founddf['attpol'].tolist()[0].split('|')[labelindex]
                foundattpol = re.search(r'^.*\[', foundattpol).group()[:-1]
            else:
                foundattpol = not_applicable
            foundgralab = not_applicable
            foundgrapol = not_applicable
        elif layer == 'gra':
            if 'gralab' in founddf.columns:
                foundgralab = founddf['gralab'].tolist()[0].split('|')[labelindex]
                foundgralab = re.search(r'^.*\[', foundgralab).group()[:-1]
            else:
                foundgralab = not_applicable
            if 'grapol' in founddf.columns:
                foundgrapol = founddf['grapol'].tolist()[0].split('|')[labelindex]
                foundgrapol = re.search(r'^.*\[', foundgrapol).group()[:-1]
            else:
                foundgrapol = not_applicable
            foundattlab = not_applicable
            foundattpol = not_applicable
        elif layer == 'neg':
            if 'negation' in founddf.columns:
                foundneglab = founddf['negation'].tolist()[0].split('|')[labelindex]
                foundneglab = re.search(r'^.*\[', foundneglab).group()[:-1]
            else:
                foundneglab = not_applicable
        else:
            print(label, "I can't tell which label this is.")

        # put all that together into a list for a new row
        if layer == 'att' or layer == 'gra':
            foundrow = [commentid, foundsentstart, foundsentend, foundcharstart, foundcharend,
                        foundwords, foundattlab, foundattpol, foundgralab, foundgrapol]
        elif layer == 'neg':
            foundrow = [commentid, foundsentstart, foundsentend, foundcharstart, foundcharend,
                        foundwords, foundneglab]
        else:
            print("I couldn't make a new row because I don't know which label this is")
        if verbose:
            print('Done with comment', commentid, "label", label)
        return foundrow

    # look for unlabelled spans (i.e. label '_')
    elif label == '_':
        if layer == 'neg':
            mask = [(label in i) for i in dataframe[column].tolist()]
            founddf = dataframe[mask]
        # If the layer is Attitude or Graduation, check for spans with a label but no polarity or vice versa
        # and be sure that any spans returned as unlabelled have no label or polarity
        elif layer == 'att' or layer == 'gra':
            attmask = []
            gramask = []
            if 'attlab' in dataframe.columns and 'attpol' in dataframe.columns:
                mask1 = [(label in i) for i in dataframe['attlab'].tolist()]
                mask2 = [(label in i) for i in dataframe['attpol'].tolist()]
                for i in range(len(mask1)):
                    if mask1[i] is not mask2[i]:
                        print('row', i, 'has mismatched Attitude labels')
                attmask = [a and b for a, b in zip(mask1, mask2)]
            if 'gralab' in dataframe.columns and 'grapol' in dataframe.columns:
                mask3 = [(label in i) for i in dataframe['gralab'].tolist()]
                mask4 = [(label in i) for i in dataframe['grapol'].tolist()]
                for i in range(len(mask3)):
                    if mask3[i] is not mask4[i]:
                        print('row', i, 'has mismatched Graduation labels')
                gramask = [a and b for a, b in zip(mask3, mask4)]
            if attmask and not gramask:
                mask = attmask
            elif gramask and not attmask:
                mask = gramask
            elif attmask and gramask:
                mask = [a and b for a, b in zip(attmask, gramask)]
            elif not attmask and not gramask:                   # this will return all rows if there's no attlab or
                mask = [True for i in range(len(dataframe))]    # gralab, since there's no annotations at all.
            founddf = dataframe[mask]
        else:
            print("Layer unrecognized when looking for unlabelled spans")
        # find the sentences
        sentences = []
        for i in range(len(founddf['sentpos'])):
            sentences.append(
                int(  # we want to do math on this later
                    re.search(
                        r'^.*-', founddf['sentpos'].tolist()[i]  # finds whatever comes before a '-'
                    ).group()[:-1]  # returns the string it found
                ))

        # find the character positions
        charpositions = []
        for i in range(len(founddf['charpos'])):
            charpositions.append(
                (int(re.search(r'^.*-', founddf['charpos'].tolist()[i]).group()[:-1]),
                 int(re.search(r'-.*$', founddf['charpos'].tolist()[i]).group()[1:]))
            )

        # find all the words
        allfoundwords = founddf['word'].tolist()

        # find consecutive unlabelled words
        foundspans = []
        span_number = -1
        last_match = False
        for i in range(len(allfoundwords)):
            if i - 1 in range(len(allfoundwords)):      # if this isn't the first word
                # check if this word came right after the last one
                if sentences[i - 1] == sentences[i] and\
                        (charpositions[i - 1][-1] == (charpositions[i][0] - 1) or\
                         charpositions[i - 1][-1] == (charpositions[i][0])):
                    if not last_match:  # if this is not a continuation of the previous span
                        span_number += 1  # keep track of the number we're on (index of foundspans)
                        # add the row for this span to foundspans
                        if layer == 'att' or layer == 'gra':
                            foundspans.append([commentid,  # comment ID
                                               sentences[i-1],  # sentence start
                                               sentences[i],  # sentence end
                                               charpositions[i-1][0],  # character start
                                               charpositions[i][-1],  # character end
                                               allfoundwords[i - 1] + ' ' + allfoundwords[i],  # words
                                               not_applicable,  # Labels are all assumed to be absent.
                                               not_applicable,  # Per earlier code, it should tell you if that is
                                               not_applicable,  # not actually the case.
                                               not_applicable, ])
                        elif layer == 'neg':
                            foundspans.append([commentid,  # comment ID
                                               sentences[i-1],  # sentence start
                                               sentences[i],  # sentence end
                                               charpositions[i-1][0],  # character start
                                               charpositions[i][-1],  # character end
                                               allfoundwords[i - 1] + ' ' + allfoundwords[i],  # words
                                               not_applicable])
                        last_match = True  # record these two i's as contiguous

                    else:  # (this word is a continuation of the previous span)
                        foundspans[span_number].pop(4)  # remove the ending char position so we can replace it
                        oldwords = foundspans[span_number].pop(4)  # remove the words from the span to replace it
                        foundspans[span_number].insert(4, charpositions[i][-1])  # add the last character of this word
                        foundspans[span_number].insert(5, oldwords + ' ' + allfoundwords[i])  # add the words together

                else:
                    last_match = False  # record these two i's as non-contiguous
                    # check if this is the first pair of words we're looking at
                    if i == 1:      # i would equal 1 bc we skip i=0 (since we looked backwards)
                        # if i=1 and the first and second words are non-contiguous, we need to add
                        # the first word to foundspans.
                        if layer == 'att' or layer == 'gra':
                            foundspans.append([commentid,  # comment ID
                                               sentences[i-1],  # sentence start
                                               sentences[i-1],  # sentence end
                                               charpositions[i-1][0],  # character start
                                               charpositions[i-1][-1],  # character end
                                               allfoundwords[i-1],  # word
                                               not_applicable,  # Labels are all assumed to be absent.
                                               not_applicable,  # Per earlier code, it should tell you if that is
                                               not_applicable,  # not actually the case.
                                               not_applicable, ])
                        elif layer == 'neg':
                            foundspans.append([commentid,  # comment ID
                                               sentences[i-1],  # sentence start
                                               sentences[i-1],  # sentence end
                                               charpositions[i-1][0],  # character start
                                               charpositions[i-1][-1],  # character end
                                               allfoundwords[i-1],  # word
                                               not_applicable])
                    # look ahead to see if the next word is a continuation of this span:
                    if i + 1 in range(len(sentences)):
                        if sentences[i + 1] != sentences[i] and charpositions[i + 1][-1] != (charpositions[i][0] + 1):
                            span_number = span_number + 1  # if so, keep track of the index
                            if layer == 'att' or layer == 'gra':
                                foundspans.append([commentid,  # comment ID
                                                   sentences[i],  # sentence start
                                                   sentences[i],  # sentence end
                                                   charpositions[i][0],  # character start
                                                   charpositions[i][-1],  # character end
                                                   allfoundwords[i],  # word
                                                   not_applicable,  # Labels are all assumed to be absent.
                                                   not_applicable,  # Per earlier code, it should tell you if that is
                                                   not_applicable,  # not actually the case.
                                                   not_applicable, ])
                            elif layer == 'neg':
                                foundspans.append([commentid,  # comment ID
                                                   sentences[i],  # sentence start
                                                   sentences[i],  # sentence end
                                                   charpositions[i][0],  # character start
                                                   charpositions[i][-1],  # character end
                                                   allfoundwords[i],  # word
                                                   not_applicable])
                        # else: the loop continues
                    else:  # if there is no following word and this one isn't a continuation, it's its own word.
                        span_number = span_number + 1
                        if layer == 'att' or layer == 'gra':
                            foundspans.append([commentid,  # comment ID
                                               sentences[i],  # sentence start
                                               sentences[i],  # sentence end
                                               charpositions[i][0],  # character start
                                               charpositions[i][-1],  # character end
                                               allfoundwords[i],  # word
                                               not_applicable,  # Labels are all assumed to be absent.
                                               not_applicable,  # Per earlier code, it should tell you if that is
                                               not_applicable,  # not actually the case.
                                               not_applicable, ])
                        elif layer == 'neg':
                            foundspans.append([commentid,  # comment ID
                                               sentences[i],  # sentence start
                                               sentences[i],  # sentence end
                                               charpositions[i][0],  # character start
                                               charpositions[i][-1],  # character end
                                               allfoundwords[i],  # word
                                               not_applicable])  # no negation
        if verbose:
            print('Done with comment', commentid, "label", label)
        return foundspans

    # look for one-word annotated spans (e.g. 'Appreciation'
    elif ((label in attlabs) or
          (label in attpols) or
          (label in gralabs) or
          (label in grapols) or
          (label in neglabs)):
        # create subset dataframe - stricter than other conditions
        mask = [(label == i) for i in dataframe[column].tolist()]
        founddf = dataframe[mask]
        # find the sentences
        sentences = []
        for i in range(len(founddf['sentpos'])):
            sentences.append(
                int(  # we want to do math on this later
                    re.search(
                        r'^.*-', founddf['sentpos'].tolist()[i]  # finds whatever comes before a '-'
                    ).group()[:-1]  # returns the string it found, minus 1 character from the end
                ))

        # find the character positions
        charpositions = []
        for i in range(len(founddf['charpos'])):
            charpositions.append(
                (int(re.search(r'^.*-', founddf['charpos'].tolist()[i]).group()[:-1]),
                 int(re.search(r'-.*$', founddf['charpos'].tolist()[i]).group()[1:]))
            )

        # find the words
        allfoundwords = founddf['word'].tolist()

        # in case of pipes, figure out which one is the real label
        posslabels = founddf[column].tolist()
        posslabels = posslabels[0]
        posslabels = posslabels.split('|')
        labelindex = posslabels.index(label)

        # now look through the columns and find the appropriate labels
        # Each column is converted to a list. The first item in the list is used to find the label.
        # This item is split by '|' in case of stacked annotations.
        # Before, we found the index of the label we want. We get the found label from this index.
        foundspans = []
        for i in range(len(founddf)):
            # since these are one word long, the starting and ending sentences are the same.
            foundsentstart = sentences[i]
            foundsentend = foundsentstart

            # find the characters the word starts and ends with
            foundcharstart = charpositions[i][0]
            foundcharend = charpositions[i][1]

            # find the word
            foundwords = allfoundwords[i]

            if layer == 'att':
                if 'attlab' in founddf.columns:
                    foundattlab = founddf['attlab'].tolist()[0].split('|')[labelindex]
                else:
                    foundattlab = not_applicable
                if 'attpol' in founddf.columns:
                    foundattpol = founddf['attpol'].tolist()[0].split('|')[labelindex]
                else:
                    foundattpol = not_applicable
                foundgralab = not_applicable
                foundgrapol = not_applicable
            elif layer == 'gra':
                if 'gralab' in founddf.columns:
                    foundgralab = founddf['gralab'].tolist()[0].split('|')[labelindex]
                else:
                    foundgralab = not_applicable
                if 'grapol' in founddf.columns:
                    foundgrapol = founddf['grapol'].tolist()[0].split('|')[labelindex]
                else:
                    foundgrapol = not_applicable
                foundattlab = not_applicable
                foundattpol = not_applicable
            elif layer == 'neg':
                if 'negation' in founddf.columns:
                    foundneglab = founddf['negation'].tolist()[0].split('|')[labelindex]
                else:
                    foundneglab = not_applicable
            else:
                print(label, "I can't tell which label this is.")

            # put all that together into a list for a new row
            if layer == 'att' or layer == 'gra':
                foundrow = [commentid, foundsentstart, foundsentend, foundcharstart, foundcharend,
                            foundwords, foundattlab, foundattpol, foundgralab, foundgrapol]
            elif layer == 'neg':
                foundrow = [commentid, foundsentstart, foundsentend, foundcharstart, foundcharend,
                            foundwords, foundneglab]
            else:
                print("I couldn't make a new row because I don't know which label this is")
            # add that row to foundspans
            foundspans.append(foundrow)

        if verbose:
            print('Done with comment', commentid, "label", label)
        return foundspans

    else:
        print('Your label was not recognized')


# you can try commands like:
"""
testdf1 = readprojfile(appraisal_projectdirs[3], 'app')
lookup_label(testdf1,'attlab','_', commentid='testdf1')
lookup_label(testdf1,'attlab','Judgment[4]', commentid='testdf1')
lookup_label(testdf1,'attlab','Appreciation', commentid='testdf1')
lookup_label(testdf1, 'gralab', 'Force', commentid='testdf1')

testdf2 = readprojfile(negation_projectdirs[3], 'neg')
lookup_label(testdf2, 'negation', 'NEG', commentid='testdf2')
lookup_label(testdf2, 'negation', 'SCOPE[2]', commentid='testdf2')
lookup_label(testdf2, 'negation', '_', commentid='testdf2')
"""

# this variable will be used in a moment; it's the same as collabels, keeping only the 'label' parts
# it's used so that we don't search polarity redundantly
appraisal_search_correspondences = (appraisal_collabels[0], appraisal_collabels[2])

# column names for new dataframes:
appraisal_newheads = ['comment',
                      'sentstart',
                      'sentend',
                      'charstart',
                      'charend',
                      'span',
                      'attlab',
                      'attpol',
                      'gralab',
                      'grapol']
negation_newheads = ['comment',
                     'sentstart',
                     'sentend',
                     'charstart',
                     'charend',
                     'span',
                     'label']


def simplify_dataframe(dataframe, project, commentid="Dataframe", not_applicable=None, bothids=True,
                       clean_suffix='_cleaned.tsv', verbose=()):
    """
    Uses all the labels in correspondences to create a new dataframe organized by span rather than by word.

    :param dataframe: the dataframe to search and re-create
    :param project: 'neg' for a negation project, 'app' for an appraisal project
    :param commentid: the name of the comment; the new row will have this as its first entry
    :param not_applicable: what to put in a cell if there is no data (e.g. something un-annotated)
    :param bothids: whether to add in a column with the other id (e.g. aboriginal_1 or source_01...)
    :param clean_suffix: the suffix added to clean files (this will be removed from commentid to find the other id)
    :param verbose: an iterable containing one or more of the following strings:
                    missingcol: reports whenever a comment lacks an annotation for one or more columns
                    label_done: reports when each label has been searched for (same as verbose for lookup_label)
                    comment_done: reports when the function has finished running
    :return: a new dataframe with the same content as the one given in the first place, but reorganized by span
        rather than by word
    """
    # set verbosity
    if 'missingcol' in verbose:
        verbose_missingcol = True
    else:
        verbose_missingcol = False

    # set newcols and correspondences
    if project == "neg" or project.lower() == "negation":
        newcols = negation_newheads
        correspondences = negation_collabels
        project = "neg"
    elif project == "app" or project.lower() == "appraisal":
        newcols = appraisal_newheads
        correspondences = appraisal_search_correspondences
        project = "app"
    else:
        print("Project type not recognized. Use 'neg' or 'app'.")
        newcols = None
        correspondences = None

    # find the labels to look for
    labinds = getlabinds_df(dataframe, correspondences=correspondences, dfname=commentid, verbose=verbose_missingcol)

    # search the old dataframe and create a list to later add as rows to the empty one
    if 'label_done' in verbose:
        v_label_done = True
    else:
        v_label_done = False
    foundrows = []
    for i in range(len(correspondences)):
        searchcolumn = correspondences[i][0]        # which column to look in
        if searchcolumn in dataframe.columns:
            searchlabels = labinds[searchcolumn]    # which labels to look for in that column
            for searchlabel in searchlabels:
                foundstuff = lookup_label(dataframe,
                                          searchcolumn,
                                          searchlabel,
                                          commentid=commentid,
                                          not_applicable=not_applicable,
                                          verbose=v_label_done)
                if '[' in searchlabel:  # in this case, foundstuff is one row of data
                    foundrows.append(foundstuff)
                else:                   # in this case, foundstuff is many rows of data
                    for row in foundstuff:
                        foundrows.append(row)

    # if foundrows is empty, then instead of returning an empty df, return a df with a None-annotated row.
    if not foundrows:
        # find the sentences
        sentences = []
        # add the first sentence number to sentences
        sentences.append(
            int(
                re.search(
                    r'^.*-', dataframe['sentpos'].tolist()[0]  # finds whatever comes before a '-'
                ).group()[:-1]  # returns the string it found
            ))
        # add the last sentence number to sentences
        sentences.append(
            int(
                re.search(
                    r'^.*-', dataframe['sentpos'].tolist()[-1]  # finds whatever comes before a '-'
                ).group()[:-1]  # returns the string it found
            ))

        # find the character positions
        charpositions = (int(re.search(r'^.*-', dataframe['charpos'].tolist()[0]).group()[:-1]),
                         int(re.search(r'-.*$', dataframe['charpos'].tolist()[-1]).group()[1:]))

        # find all the words
        allfoundwords = dataframe['word'].tolist()
        allfoundwords = " ".join(allfoundwords)

        if project == "app":
            foundrows.append([commentid,  # comment ID
                              sentences[0],  # sentence start
                              sentences[1],  # sentence end
                              charpositions[0],  # character start
                              charpositions[1],  # character end
                              allfoundwords,  # word
                              not_applicable,  # Labels are all assumed to be absent.
                              not_applicable,
                              not_applicable,
                              not_applicable, ])
        elif project == "neg":
            foundrows.append([commentid,  # comment ID
                              sentences[0],  # sentence start
                              sentences[1],  # sentence end
                              charpositions[0],  # character start
                              charpositions[1],  # character end
                              allfoundwords,  # word
                              not_applicable])  # no negation

    # make the rows into a new df
    newdf = pd.DataFrame(foundrows, columns=newcols)
    # sort by which character the row starts with in ascending order, then which character it ends with descending
    # this means that it will read chronologically, with longer spans appearing first
    newdf = newdf.sort_values(by=['charstart', 'charend'], ascending=[True, False])
    # lookup_label will return duplicate rows when there is a span annotated only for Attitude or only for Graduation.
    newdf = newdf.drop_duplicates()
    # now, if necessary, add a column for the other comment id
    if bothids:
        commentid = commentid[:-len(clean_suffix)] + '.txt'
        if commentid in mappingdict1:
            otherid = mappingdict1[commentid]
        elif commentid in mappingdict2:
            otherid = mappingdict2[commentid]
        else:
            otherid=''
            print("No other comment id found for", commentid + '.')
        if otherid:
            newdf['comment_counter'] = otherid
    if 'comment_done' in verbose:
        print(commentid, "processed")
    return newdf

# try simplify_dataframe(testdf1, appraisal_newheads, appraisal_search_correspondences, commentid="testdf1")


def combine_annotations(paths, project, not_applicable=None, bothids=True, clean_suffix='_cleaned.tsv', verbose=()):
    """
    Takes cleaned WebAnno TSVs from given paths and reorganizes them into one single dataframe, with each row
    representing a span (not a word, as original TSV rows do).

    :param paths: where your cleaned WebAnno TSVs can be found
    :param project: 'neg' for a negation project, 'app' for an appraisal project
    :param not_applicable: what to put in a cell if there is no data (e.g. something un-annotated)
    :param bothids: whether to include a column with the other form of identification (see simplify_dataframe())
    :param clean_suffix: the suffix for cleaned files (this is removed if bothids is True, so that the mapping
                        dictionaries work.) (see simplify_dataframe()).
    :param verbose: an iterable containing one or more of the following strings:
                    missingcol: reports whenever a comment lacks an annotation for one or more columns
                    label_done: reports when each label has been searched for (same as verbose for lookup_label)
                    comment_start: before processing a comment, reports which commentid it is about to process
                    comment_done: reports when the function has finished with each comment
                    all_done: reports when the function is finished running
    :return: A new dataframe incorporating the information of all the TSVs in paths. Each row of the dataframe is one
        span.
    """
    # set newcols and correspondences
    if project.lower() == "neg" or project.lower() == "negation":
        newcols = negation_newheads
        project = "neg"
    elif project.lower() == "app" or project.lower() == "appraisal":
        newcols = appraisal_newheads
        project = "app"
    else:
        print("Project type not recognized. Use 'neg' or 'app'.")
        newcols = None

    newdf = pd.DataFrame(columns=newcols)
    for path in paths:
        commentid = path.split('/')[-1]
        if 'comment_start' in verbose:
            print("Processing comment", commentid)
        originaldf = readprojfile(path, project)
        founddf = simplify_dataframe(originaldf,
                                     project,
                                     commentid=commentid,
                                     bothids=bothids,
                                     clean_suffix=clean_suffix,
                                     not_applicable=not_applicable,
                                     verbose=verbose)
        newdf = newdf.append(founddf)
    if 'all_done' in verbose:
        print("New dataframe created.")
    return newdf
# try combine_annotations(testdirs, 'app')


if appraisal_projectpath:
    if mapping_csv:
        combined_appraisal_dataframe = combine_annotations(appraisal_projectdirs,
                                                           'app',
                                                           not_applicable='None',   # a string works better for R
                                                           verbose=('comment_start',))
        if appraisal_writepath:
            combined_appraisal_dataframe.to_csv(appraisal_writepath)
            print("Appraisal dataframe exported.")
        else:
            print("Not exporting Appraisal project as no path was specified.")
    else:
        combined_appraisal_dataframe = combine_annotations(appraisal_projectdirs,
                                                           'app',
                                                           not_applicable='None',
                                                           bothids=False,
                                                           verbose=('comment_start',))
        if appraisal_writepath:
            combined_appraisal_dataframe.to_csv(appraisal_writepath)
            print("Appraisal dataframe exported.")
        else:
            print("Not exporting Appraisal project as no path was specified.")
else:
    print("Not combining Appraisal project as no path was specified.")

if negation_projectpath:
    combined_negation_dataframe = combine_annotations(negation_projectdirs,
                                                      'neg',
                                                      not_applicable='None',
                                                      verbose=('comment_start',))
    if negation_writepath:
        combined_negation_dataframe.to_csv(negation_writepath)
        print("Negation dataframe exported.")
    else:
        print("Not exporting Negation project as no path was specified.")
else:
    print("Not combining Negation project as no path was specified.")
