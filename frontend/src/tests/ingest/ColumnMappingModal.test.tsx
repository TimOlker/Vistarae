import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import {
  ColumnMappingModal,
  suggestFieldMapping,
  parseCSVLine,
} from "../../components/ingest/ColumnMappingModal";

describe("ColumnMappingModal utilities", () => {
  it("parses CSV lines correctly with quotes and commas", () => {
    const line = 'Colosseum,"Rome, Italy",41.8902,12.4922,"Ancient amphitheatre, gladiators"';
    const parsed = parseCSVLine(line);
    expect(parsed).toEqual([
      "Colosseum",
      "Rome, Italy",
      "41.8902",
      "12.4922",
      "Ancient amphitheatre, gladiators",
    ]);
  });

  it("suggests correct Vistarae fields based on header synonyms", () => {
    expect(suggestFieldMapping("Wonder")).toBe("poi_name");
    expect(suggestFieldMapping("Wonders of the World")).toBe("poi_name");
    expect(suggestFieldMapping("Attraction")).toBe("poi_name");
    expect(suggestFieldMapping("Monument Name")).toBe("poi_name");
    expect(suggestFieldMapping("Locality")).toBe("city");
    expect(suggestFieldMapping("Town")).toBe("city");
    expect(suggestFieldMapping("Country")).toBe("country");
    expect(suggestFieldMapping("Lat")).toBe("latitude");
    expect(suggestFieldMapping("Long")).toBe("longitude");
    expect(suggestFieldMapping("Notes")).toBe("description");
    expect(suggestFieldMapping("RandomColumnXYZ")).toBe("");
  });
});

describe("ColumnMappingModal Component", () => {
  it("renders discovered headers and sample row previews", async () => {
    const csvContent = "Wonder,Locality,Country,Notes\nGreat Wall,Beijing,China,Historic fortification";
    const file = new File([csvContent], "new_wonders_of_the_world.csv", { type: "text/csv" });
    file.text = async () => csvContent;
    const onClose = vi.fn();
    const onApplyMapping = vi.fn();

    render(
      <ColumnMappingModal
        isOpen={true}
        onClose={onClose}
        file={file}
        onApplyMapping={onApplyMapping}
      />,
    );

    expect(screen.getByText("Map Travel Point Columns")).toBeInTheDocument();
    expect(screen.getByText("Unmapped Columns Detected")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("select-mapping-Wonder")).toBeInTheDocument();
      expect(screen.getByTestId("select-mapping-Locality")).toBeInTheDocument();
      expect(screen.getByTestId("select-mapping-Country")).toBeInTheDocument();
      expect(screen.getByTestId("select-mapping-Notes")).toBeInTheDocument();
      expect(screen.getByText("Beijing")).toBeInTheDocument();
      expect(screen.getByText("Historic fortification")).toBeInTheDocument();
    });

    // Auto-detection should have mapped "Wonder" to "poi_name"
    const applyBtn = screen.getByTestId("apply-column-mapping-btn");
    expect(applyBtn).not.toBeDisabled();
    expect(screen.getByText('Ready: "POI Name" is assigned.')).toBeInTheDocument();
  });

  it("disables Apply button when POI Name is not mapped and enables when selected", async () => {
    const csvContent = "Col_A,Col_B\nVal_1,Val_2";
    const file = new File([csvContent], "custom.csv", { type: "text/csv" });
    file.text = async () => csvContent;
    const onClose = vi.fn();
    const onApplyMapping = vi.fn();

    render(
      <ColumnMappingModal
        isOpen={true}
        onClose={onClose}
        file={file}
        onApplyMapping={onApplyMapping}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Col_A")).toBeInTheDocument();
    });

    const applyBtn = screen.getByTestId("apply-column-mapping-btn");
    // Initially Col_A and Col_B do not auto-map to poi_name
    expect(applyBtn).toBeDisabled();
    expect(
      screen.getByText('Action Required: Please assign at least one column to "POI Name (Required)".'),
    ).toBeInTheDocument();

    // Map Col_A to poi_name
    const selectA = screen.getByTestId("select-mapping-Col_A");
    fireEvent.change(selectA, { target: { value: "poi_name" } });

    expect(applyBtn).not.toBeDisabled();
    expect(screen.getByText('Ready: "POI Name" is assigned.')).toBeInTheDocument();

    // Click Apply Mapping & Import
    fireEvent.click(applyBtn);

    expect(onApplyMapping).toHaveBeenCalledTimes(1);
    const [mappedFile, mapping] = onApplyMapping.mock.calls[0];
    expect(mapping).toEqual({
      Col_A: "poi_name",
      Col_B: "",
    });
    expect(mappedFile.name).toBe("custom.csv");
  });
});
