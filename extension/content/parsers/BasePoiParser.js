// Copyright (c) 2026 Tim Olker
// SPDX-License-Identifier: Apache-2.0

/**
 * @typedef {Object} ExtractedPoi
 * @property {string} name
 * @property {string} [description]
 * @property {string} [category]
 * @property {string} [address]
 * @property {string} [city]
 * @property {string} [state]
 * @property {string} [country]
 * @property {number | null} [latitude]
 * @property {number | null} [longitude]
 * @property {number | null} [rating]
 * @property {number | null} [physical_effort]
 * @property {number | null} [cost_tier]
 * @property {string} [best_time]
 * @property {string[]} [tags]
 * @property {string} [source_url]
 * @property {string[]} [photo_urls]
 */

/**
 * Abstract Base Class for all travel POI parsers.
 */
export class BasePoiParser {
  /**
   * @param {string} name - Identifying name of the parser.
   */
  constructor(name = "BasePoiParser") {
    this.name = name;
  }

  /**
   * Evaluates whether this parser can handle the provided URL and DOM.
   * @param {string} url - Active tab location URL string.
   * @param {Document} document - DOM document object.
   * @returns {boolean}
   */
  canParse(url, document) {
    return false;
  }

  /**
   * Extracts structured POI attributes from the document and highlighted text.
   * @param {Document} document - DOM document object.
   * @param {string} [selectionText] - Currently highlighted text.
   * @param {string} [url] - Active URL string.
   * @returns {ExtractedPoi}
   */
  parse(document, selectionText = "", url = "") {
    throw new Error("Abstract method parse() must be implemented by subclass.");
  }
}

/**
 * Global registry holding registered parser instances in priority order.
 * @type {BasePoiParser[]}
 */
export const parserRegistry = [];

/**
 * Registers a parser class instance into the registry.
 * @param {BasePoiParser} parser
 */
export function registerParser(parser) {
  if (
    parser instanceof BasePoiParser &&
    !parserRegistry.some((p) => p.name === parser.name)
  ) {
    parserRegistry.push(parser);
  }
}

/**
 * Finds the first registered parser that matches the current page.
 * @param {string} url
 * @param {Document} document
 * @returns {BasePoiParser | null}
 */
export function findParserForUrl(url, document) {
  for (const parser of parserRegistry) {
    try {
      if (parser.canParse(url, document)) {
        return parser;
      }
    } catch (err) {
      console.warn(`Error evaluating parser ${parser.name}:`, err);
    }
  }
  return null;
}
