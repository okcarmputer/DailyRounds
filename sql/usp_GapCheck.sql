CREATE OR ALTER PROCEDURE dbo.usp_GapCheck
    @TableName NVARCHAR(128),
    @DateColumn NVARCHAR(128),
    @ExpectedRowsPerDay INT
AS
BEGIN
    DECLARE @sql NVARCHAR(MAX);
    SET @sql = N'
    ;WITH Bounds AS (
        SELECT CAST(MIN(' + QUOTENAME(@DateColumn) + N') AS date) AS MinDay,
               CAST(MAX(' + QUOTENAME(@DateColumn) + N') AS date) AS MaxDay
        FROM ' + QUOTENAME(@TableName) + N'
    ),
    AllDays AS (
        SELECT MinDay AS [Day], MaxDay FROM Bounds
        UNION ALL
        SELECT DATEADD(DAY, 1, [Day]), MaxDay FROM AllDays WHERE [Day] < MaxDay
    )
    SELECT ad.[Day],
           ISNULL(t.[DayRowCount], 0) AS DayRowCount,
           ' + CAST(@ExpectedRowsPerDay AS NVARCHAR) + N' AS ExpectedRowCount
    FROM AllDays ad
    LEFT JOIN (
        SELECT CAST(' + QUOTENAME(@DateColumn) + N' AS date) AS [Day], COUNT(*) AS DayRowCount
        FROM ' + QUOTENAME(@TableName) + N'
        GROUP BY CAST(' + QUOTENAME(@DateColumn) + N' AS date)
    ) t ON t.[Day] = ad.[Day]
    WHERE ISNULL(t.[DayRowCount], 0) < ' + CAST(@ExpectedRowsPerDay AS NVARCHAR) + N'
    ORDER BY ad.[Day]
    OPTION (MAXRECURSION 0);';
    EXEC sp_executesql @sql;
END
